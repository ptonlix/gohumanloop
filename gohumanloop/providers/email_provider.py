import asyncio
import smtplib
import imaplib
import email
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, Any, Optional, List, Tuple
import re
import time
from datetime import datetime, timedelta

from gohumanloop.providers.base import BaseProvider
from gohumanloop.core.interface import ApprovalResult, ApprovalStatus
from gohumanloop.utils.context_formatter import ContextFormatter

class EmailProvider(BaseProvider):
    """通过电子邮件实现人机交互的提供者"""
    
    def __init__(
        self,
        smtp_server: str,
        smtp_port: int,
        imap_server: str,
        imap_port: int,
        username: str,
        password: str,
        recipients: List[str],
        check_interval: float = 60.0,
        **kwargs
    ):
        super().__init__(kwargs.get("config"))
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.imap_server = imap_server
        self.imap_port = imap_port
        self.username = username
        self.password = password
        self.recipients = recipients
        self.check_interval = check_interval
        self.polling_task = None
        self.approval_pattern = re.compile(r'APPROVE:([a-zA-Z0-9-]+)')
        self.rejection_pattern = re.compile(r'REJECT:([a-zA-Z0-9-]+)')
        self.feedback_pattern = re.compile(r'FEEDBACK:(.*?)(?=APPROVE:|REJECT:|$)', re.DOTALL)
        
    async def start_polling(self):
        """启动邮件轮询任务"""
        if self.polling_task is None:
            self.polling_task = asyncio.create_task(self._poll_emails())
            
    async def stop_polling(self):
        """停止邮件轮询任务"""
        if self.polling_task:
            self.polling_task.cancel()
            self.polling_task = None
            
    async def _poll_emails(self):
        """轮询邮件以检查批准响应"""
        while True:
            try:
                # 连接到IMAP服务器
                mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
                mail.login(self.username, self.password)
                mail.select('inbox')
                
                # 搜索未读邮件
                status, messages = mail.search(None, 'UNSEEN')
                
                if status == 'OK':
                    for num in messages[0].split():
                        status, data = mail.fetch(num, '(RFC822)')
                        if status == 'OK':
                            msg = email.message_from_bytes(data[0][1])
                            subject = msg['subject']
                            
                            # 检查是否是批准响应
                            if subject and 'Re: Approval Request' in subject:
                                body = ""
                                if msg.is_multipart():
                                    for part in msg.walk():
                                        content_type = part.get_content_type()
                                        if content_type == 'text/plain':
                                            body = part.get_payload(decode=True).decode()
                                            break
                                else:
                                    body = msg.get_payload(decode=True).decode()
                                    
                                # 解析批准/拒绝和反馈
                                approve_match = self.approval_pattern.search(body)
                                reject_match = self.rejection_pattern.search(body)
                                feedback_match = self.feedback_pattern.search(body)
                                
                                request_id = None
                                status = None
                                
                                if approve_match:
                                    request_id = approve_match.group(1)
                                    status = ApprovalStatus.APPROVED
                                elif reject_match:
                                    request_id = reject_match.group(1)
                                    status = ApprovalStatus.REJECTED
                                    
                                if request_id and status and request_id in self._requests:
                                    feedback = feedback_match.group(1).strip() if feedback_match else ""
                                    
                                    # 更新请求状态
                                    self._requests[request_id]["status"] = status
                                    self._requests[request_id]["feedback"] = feedback
                                    self._requests[request_id]["approved_at"] = datetime.now().isoformat()
                                    self._requests[request_id]["approved_by"] = msg['from']
                
                mail.close()
                mail.logout()
            except Exception:
                pass  # 忽略错误，继续轮询
                
            await asyncio.sleep(self.check_interval)
            
    async def _send_approval_email(
        self, 
        request_id: str, 
        task_id: str, 
        context: Dict[str, Any],
        timeout: Optional[int] = None
    ):
        """发送批准请求邮件"""
        # 格式化上下文
        formatted_context = ContextFormatter.format_for_human(context)
        
        # 构建邮件
        msg = MIMEMultipart()
        msg['From'] = self.username
        msg['To'] = ', '.join(self.recipients)
        msg['Subject'] = f"Approval Request: {task_id} [{request_id}]"
        
        # 构建邮件正文
        body = f"""
        您收到了一个批准请求：
        
        任务ID: {task_id}
        请求ID: {request_id}
        
        {formatted_context}
        
        请回复此邮件并包含以下内容之一：
        
        批准: APPROVE:{request_id}
        拒绝: REJECT:{request_id}
        
        您也可以提供反馈：
        FEEDBACK:您的反馈内容
        
        """
        if timeout:
            expiry_time = datetime.now() + timedelta(seconds=timeout)
            body += f"\n请求将在 {expiry_time.strftime('%Y-%m-%d %H:%M:%S')} 过期。"
            
        msg.attach(MIMEText(body, 'plain'))
        
        # 发送邮件
        try:
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.username, self.password)
            server.send_message(msg)
            server.quit()
            return True
        except Exception:
            return False
            
    async def request_approval(
        self,
        task_id: str,
        context: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None
    ) -> ApprovalResult:
        """通过电子邮件请求人类批准"""
        request_id = self._generate_request_id()
        metadata = metadata or {}
        
        # 存储请求信息
        self._store_request(request_id, task_id, context, metadata, timeout)
        
        # 确保轮询任务正在运行
        await self.start_polling()
        
        # 发送批准请求邮件
        success = await self._send_approval_email(request_id, task_id, context, timeout)
        
        if success:
            return ApprovalResult(
                request_id=request_id,
                status=ApprovalStatus.PENDING
            )
        else:
            return ApprovalResult(
                request_id=request_id,
                status=ApprovalStatus.ERROR,
                error="Failed to send approval email"
            )
            
    async def check_approval_status(self, request_id: str) -> ApprovalResult:
        """检查批准状态"""
        if request_id not in self._requests:
            return ApprovalResult(
                request_id=request_id,
                status=ApprovalStatus.ERROR,
                error="Request not found"
            )
            
        request = self._requests[request_id]
        
        # 检查是否超时
        if request["timeout"]:
            created_at = datetime.fromisoformat(request["created_at"])
            if (datetime.now() - created_at).total_seconds() > request["timeout"]:
                return ApprovalResult(
                    request_id=request_id,
                    status=ApprovalStatus.EXPIRED,
                    error="Request expired"
                )
                
        # 返回当前状态
        return ApprovalResult(
            request_id=request_id,
            status=request["status"],
            feedback=request.get("feedback"),
            approved_by=request.get("approved_by"),
            approved_at=request.get("approved_at")
        )