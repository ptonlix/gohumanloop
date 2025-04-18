import asyncio
import smtplib
import imaplib
import email
import email.mime.multipart
import email.mime.text
import time
import logging
import uuid
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime

from gohumanloop.core.interface import (
    HumanLoopProvider, HumanLoopResult, HumanLoopStatus, HumanLoopType
)
from gohumanloop.providers.base import BaseProvider

logger = logging.getLogger(__name__)

class EmailProvider(BaseProvider):
    """基于电子邮件的人机循环提供者实现"""
    
    def __init__(
        self,
        name: str,
        smtp_server: str,
        smtp_port: int,
        imap_server: str,
        imap_port: int,
        username: str,
        password: str,
        sender_email: Optional[str] = None,
        check_interval: int = 60,
        config: Optional[Dict[str, Any]] = None
    ):
        """初始化 Email 提供者
        
        Args:
            name: 提供者名称
            smtp_server: SMTP 服务器地址
            smtp_port: SMTP 服务器端口
            imap_server: IMAP 服务器地址
            imap_port: IMAP 服务器端口
            username: 邮箱用户名
            password: 邮箱密码
            sender_email: 发件人邮箱（如果与用户名不同）
            check_interval: 检查邮件的时间间隔（秒）
            config: 其他配置参数
        """
        super().__init__(name, config)
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.imap_server = imap_server
        self.imap_port = imap_port
        self.username = username
        self.password = password
        self.sender_email = sender_email or username
        self.check_interval = check_interval
        
        # 存储邮件主题与请求ID的映射关系
        self._subject_to_request = {}
        # 存储正在运行的邮件检查任务
        self._mail_check_tasks = {}
        # 存储邮件会话ID与对话ID的映射
        self._thread_to_conversation = {}
        
    async def _send_email(
        self, 
        to_email: str, 
        subject: str, 
        body: str,
        html_body: Optional[str] = None,
        reply_to: Optional[str] = None
    ) -> bool:
        """发送电子邮件
        
        Args:
            to_email: 收件人邮箱
            subject: 邮件主题
            body: 邮件正文（纯文本）
            html_body: 邮件正文（HTML格式，可选）
            reply_to: 回复邮件ID（可选）
            
        Returns:
            bool: 发送是否成功
        """
        try:
            msg = email.mime.multipart.MIMEMultipart('alternative')
            msg['From'] = self.sender_email
            msg['To'] = to_email
            msg['Subject'] = subject
            
            # 添加纯文本内容
            msg.attach(email.mime.text.MIMEText(body, 'plain'))
            
            # 如果提供了HTML内容，也添加HTML版本
            if html_body:
                msg.attach(email.mime.text.MIMEText(html_body, 'html'))
                
            # 如果是回复邮件，添加相关邮件头
            if reply_to:
                msg['In-Reply-To'] = reply_to
                msg['References'] = reply_to
            
            # 使用异步方式发送邮件
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self._send_email_sync,
                msg
            )
            return True
        except Exception as e:
            logger.error(f"发送邮件失败: {str(e)}")
            return False
            
    def _send_email_sync(self, msg):
        """同步发送邮件（在执行器中运行）"""
        with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
            server.starttls()
            server.login(self.username, self.password)
            server.send_message(msg)
            
    async def _check_emails(self, conversation_id: str, request_id: str, recipient_email: str, subject: str):
        """检查邮件回复
        
        Args:
            conversation_id: 对话ID
            request_id: 请求ID
            recipient_email: 收件人邮箱
            subject: 邮件主题
        """
        request_key = (conversation_id, request_id)
        
        while request_key in self._requests and self._requests[request_key]["status"] in [
            HumanLoopStatus.PENDING, HumanLoopStatus.INPROGRESS
        ]:
            try:
                # 使用异步方式检查邮件
                loop = asyncio.get_event_loop()
                emails = await loop.run_in_executor(
                    None,
                    self._fetch_emails_sync,
                    subject,
                    recipient_email
                )
                
                if emails:
                    # 找到回复邮件，处理响应
                    for email_msg in emails:
                        await self._process_email_response(conversation_id, request_id, email_msg)
                    break
                    
                # 等待一段时间后再次检查
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"检查邮件失败: {str(e)}")
                # 更新请求状态为错误
                if request_key in self._requests:
                    self._requests[request_key]["status"] = HumanLoopStatus.ERROR
                    self._requests[request_key]["error"] = f"检查邮件失败: {str(e)}"
                break
                
    def _fetch_emails_sync(self, subject: str, sender_email: Optional[str] = None) -> List[email.message.Message]:
        """同步获取邮件（在执行器中运行）
        
        Args:
            subject: 邮件主题
            sender_email: 发件人邮箱（可选过滤条件）
            
        Returns:
            List[email.message.Message]: 匹配的邮件列表
        """
        result = []
        try:
            # 连接到IMAP服务器
            mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            mail.login(self.username, self.password)
            mail.select('inbox')
            
            # 构建搜索条件
            search_criteria = []
            if subject:
                search_criteria.append(f'SUBJECT "{subject}"')
            if sender_email:
                search_criteria.append(f'FROM "{sender_email}"')
                
            search_str = ' '.join(search_criteria) if search_criteria else 'ALL'
            
            # 搜索邮件
            status, data = mail.search(None, search_str)
            if status != 'OK':
                logger.error(f"搜索邮件失败: {status}")
                return result
                
            # 获取邮件内容
            for num in data[0].split():
                status, data = mail.fetch(num, '(RFC822)')
                if status != 'OK':
                    continue
                    
                msg = email.message_from_bytes(data[0][1])
                result.append(msg)
                
            mail.close()
            mail.logout()
        except Exception as e:
            logger.error(f"获取邮件失败: {str(e)}")
            
        return result
        
    async def _process_email_response(self, conversation_id: str, request_id: str, email_msg: email.message.Message):
        """处理邮件响应
        
        Args:
            conversation_id: 对话ID
            request_id: 请求ID
            email_msg: 邮件消息对象
        """
        request_key = (conversation_id, request_id)
        if request_key not in self._requests:
            return
            
        # 提取邮件内容
        body = ""
        html_body = ""
        
        if email_msg.is_multipart():
            for part in email_msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))
                
                # 跳过附件
                if "attachment" in content_disposition:
                    continue
                    
                # 获取邮件内容
                payload = part.get_payload(decode=True)
                if payload is None:
                    continue
                    
                if content_type == "text/plain":
                    body = payload.decode()
                elif content_type == "text/html":
                    html_body = payload.decode()
        else:
            # 非多部分邮件
            payload = email_msg.get_payload(decode=True)
            if payload:
                body = payload.decode()
                
        # 提取发件人信息
        from_header = email_msg.get("From", "")
        responded_by = from_header.split("<")[0].strip()
        if not responded_by and "<" in from_header and ">" in from_header:
            responded_by = from_header.split("<")[1].split(">")[0].strip()
            
        # 更新请求状态
        self._requests[request_key].update({
            "status": HumanLoopStatus.COMPLETED,
            "response": {
                "text": body,
                "html": html_body,
                "subject": email_msg.get("Subject", ""),
                "from": from_header,
                "date": email_msg.get("Date", ""),
                "message_id": email_msg.get("Message-ID", "")
            },
            "responded_by": responded_by,
            "responded_at": datetime.now().isoformat()
        })
        
        # 取消超时任务
        if request_key in self._timeout_tasks:
            self._timeout_tasks[request_key].cancel()
            del self._timeout_tasks[request_key]
            
    def _format_email_body(self, context: Dict[str, Any], loop_type: HumanLoopType) -> Tuple[str, str]:
        """格式化邮件正文
        
        Args:
            context: 上下文信息
            loop_type: 循环类型
            
        Returns:
            Tuple[str, str]: (纯文本正文, HTML正文)
        """
        # 提取上下文中的内容
        message = context.get("message", "")
        question = context.get("question", "")
        options = context.get("options", [])
        
        # 构建纯文本正文
        text_body = []
        if message:
            text_body.append(message)
            text_body.append("")
            
        if question:
            text_body.append(f"问题: {question}")
            text_body.append("")
            
        if options and loop_type == HumanLoopType.APPROVAL:
            text_body.append("请选择以下选项之一:")
            for i, option in enumerate(options, 1):
                text_body.append(f"{i}. {option}")
            text_body.append("")
            text_body.append("请在回复中明确选择的选项编号。")
        elif loop_type == HumanLoopType.INFORMATION:
            text_body.append("请在回复中提供所需的信息。")
        elif loop_type == HumanLoopType.CONVERSATION:
            text_body.append("请回复此邮件继续对话。")
            
        # 构建HTML正文
        html_body = ["<html><body>"]
        if message:
            html_body.append(f"<p>{message}</p>")
            
        if question:
            html_body.append(f"<p><strong>问题:</strong> {question}</p>")
            
        if options and loop_type == HumanLoopType.APPROVAL:
            html_body.append("<p><strong>请选择以下选项之一:</strong></p>")
            html_body.append("<ol>")
            for option in options:
                html_body.append(f"<li>{option}</li>")
            html_body.append("</ol>")
            html_body.append("<p>请在回复中明确选择的选项编号。</p>")
        elif loop_type == HumanLoopType.INFORMATION:
            html_body.append("<p>请在回复中提供所需的信息。</p>")
        elif loop_type == HumanLoopType.CONVERSATION:
            html_body.append("<p>请回复此邮件继续对话。</p>")
            
        html_body.append("</body></html>")
        
        return "\n".join(text_body), "\n".join(html_body)
        
    async def request_humanloop(
        self,
        task_id: str,
        conversation_id: str,
        loop_type: HumanLoopType,
        context: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None
    ) -> HumanLoopResult:
        """请求人机循环
        
        Args:
            task_id: 任务标识符
            conversation_id: 对话ID，用于多轮对话
            loop_type: 循环类型
            context: 提供给人类的上下文信息
            metadata: 附加元数据
            timeout: 请求超时时间（秒）
            
        Returns:
            HumanLoopResult: 包含请求ID和初始状态的结果对象
        """
        metadata = metadata or {}
        
        # 生成请求ID
        request_id = self._generate_request_id()
        
        # 获取收件人邮箱
        recipient_email = metadata.get("recipient_email")
        if not recipient_email:
            return HumanLoopResult(
                conversation_id=conversation_id,
                request_id=request_id,
                loop_type=loop_type,
                status=HumanLoopStatus.ERROR,
                error="缺少收件人邮箱地址"
            )
            
        # 生成邮件主题
        subject_prefix = metadata.get("subject_prefix", f"[{self.name}]")
        subject = metadata.get("subject", f"{subject_prefix} 任务 {task_id}")
        
        # 如果是继续对话，使用相同的主题
        if conversation_id in self._conversations:
            previous_requests = self._get_conversation_requests(conversation_id)
            if previous_requests:
                last_request_id = previous_requests[-1]
                last_request_key = (conversation_id, last_request_id)
                if last_request_key in self._requests:
                    last_metadata = self._requests[last_request_key].get("metadata", {})
                    if "subject" in last_metadata:
                        subject = last_metadata["subject"]
                        
        # 格式化邮件正文
        body, html_body = self._format_email_body(context, loop_type)
        
        # 存储请求信息
        self._store_request(
            conversation_id=conversation_id,
            request_id=request_id,
            task_id=task_id,
            loop_type=loop_type,
            context=context,
            metadata={**metadata, "subject": subject, "recipient_email": recipient_email},
            timeout=timeout
        )
        
        # 发送邮件
        success = await self._send_email(
            to_email=recipient_email,
            subject=subject,
            body=body,
            html_body=html_body
        )
        
        if not success:
            # 更新请求状态为错误
            request_key = (conversation_id, request_id)
            if request_key in self._requests:
                self._requests[request_key]["status"] = HumanLoopStatus.ERROR
                self._requests[request_key]["error"] = "发送邮件失败"
                
            return HumanLoopResult(
                conversation_id=conversation_id,
                request_id=request_id,
                loop_type=loop_type,
                status=HumanLoopStatus.ERROR,
                error="发送邮件失败"
            )
            
        # 存储主题与请求的映射关系
        self._subject_to_request[subject] = (conversation_id, request_id)
        
        # 创建邮件检查任务
        check_task = asyncio.create_task(
            self._check_emails(conversation_id, request_id, recipient_email, subject)
        )
        self._mail_check_tasks[(conversation_id, request_id)] = check_task
        
        # 如果设置了超时，创建超时任务
        if timeout:
            self._create_timeout_task(conversation_id, request_id, timeout)
            
        return HumanLoopResult(
            conversation_id=conversation_id,
            request_id=request_id,
            loop_type=loop_type,
            status=HumanLoopStatus.PENDING
        )
        
    async def check_request_status(
        self,
        conversation_id: str,
        request_id: str
    ) -> HumanLoopResult:
        """检查请求状态
        
        Args:
            conversation_id: 对话标识符，用于关联多轮对话
            request_id: 请求标识符，用于标识具体的交互请求
            
        Returns:
            HumanLoopResult: 包含当前请求状态的结果对象，包括状态、响应数据等信息
        """
        request_info = self._get_request(conversation_id, request_id)
        if not request_info:
            return HumanLoopResult(
                conversation_id=conversation_id,
                request_id=request_id,
                loop_type=HumanLoopType.CONVERSATION,
                status=HumanLoopStatus.ERROR,
                error=f"Request '{request_id}' not found in conversation '{conversation_id}'"
            )
            
        # 构建结果对象
        result = HumanLoopResult(
            conversation_id=conversation_id,
            request_id=request_id,
            loop_type=request_info.get("loop_type", HumanLoopType.CONVERSATION),
            status=request_info.get("status", HumanLoopStatus.PENDING)
        )
        
        # 如果有响应数据，添加到结果中
        if "response" in request_info:
            result.response = request_info["response"]
            
        # 如果有错误信息，添加到结果中
        if "error" in request_info:
            result.error = request_info["error"]
            
        # 如果有响应者信息，添加到结果中
        if "responded_by" in request_info:
            result.responded_by = request_info["responded_by"]
            
        # 如果有响应时间，添加到结果中
        if "responded_at" in request_info:
            result.responded_at = request_info["responded_at"]
            
        return result
        
    async def continue_humanloop(
        self,
        conversation_id: str,
        context: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> HumanLoopResult:
        """继续人机循环
        
        Args:
            conversation_id: 对话ID，用于多轮对话
            context: 提供给人类的上下文信息
            metadata: 附加元数据
            timeout: 请求超时时间（秒）
            
        Returns:
            HumanLoopResult: 包含请求ID和状态的结果对象
        """
        # 检查对话是否存在
        conversation_info = self._get_conversation(conversation_id)
        if not conversation_info:
            return HumanLoopResult(
                conversation_id=conversation_id,
                request_id="",
                loop_type=HumanLoopType.CONVERSATION,
                status=HumanLoopStatus.ERROR,
                error=f"Conversation '{conversation_id}' not found"
            )
            
        # 获取任务ID
        task_id = conversation_info.get("task_id", "")
        
        # 获取上一个请求的信息
        previous_requests = self._get_conversation_requests(conversation_id)
        if not previous_requests:
            return HumanLoopResult(
                conversation_id=conversation_id,
                request_id="",
                loop_type=HumanLoopType.CONVERSATION,
                status=HumanLoopStatus.ERROR,
                error=f"No previous requests found in conversation '{conversation_id}'"
            )
            
        last_request_id = previous_requests[-1]
        last_request_key = (conversation_id, last_request_id)
        
        if last_request_key not in self._requests:
            return HumanLoopResult(
                conversation_id=conversation_id,
                request_id="",
                loop_type=HumanLoopType.CONVERSATION,
                status=HumanLoopStatus.ERROR,
                error=f"Last request '{last_request_id}' not found in conversation '{conversation_id}'"
            )
            
        last_request_info = self._requests[last_request_key]
        last_metadata = last_request_info.get("metadata", {})
        
        # 合并元数据
        merged_metadata = {**last_metadata}
        if metadata:
            merged_metadata.update(metadata)
            
        # 使用上一个请求的循环类型
        loop_type = last_request_info.get("loop_type", HumanLoopType.CONVERSATION)
        
        # 发起新的请求
        return await self.request_humanloop(
            task_id=task_id,
            conversation_id=conversation_id,
            loop_type=loop_type,
            context=context,
            metadata=merged_metadata,
            timeout=timeout
        )
        
    async def cancel_request(
        self,
        conversation_id: str,
        request_id: str
    ) -> bool:
        """取消人机循环请求
        
        Args:
            conversation_id: 对话标识符，用于关联多轮对话
            request_id: 请求标识符，用于标识具体的交互请求
            
        Returns:
            bool: 取消是否成功，True表示取消成功，False表示取消失败
        """
        # 取消邮件检查任务
        request_key = (conversation_id, request_id)
        if request_key in self._mail_check_tasks:
            self._mail_check_tasks[request_key].cancel()
            del self._mail_check_tasks[request_key]
            
        # 调用父类方法取消请求
        return await super().cancel_request(conversation_id, request_id)
        
    async def cancel_conversation(
        self,
        conversation_id: str
    ) -> bool:
        """取消整个对话
        
        Args:
            conversation_id: 对话标识符
            
        Returns:
            bool: 取消是否成功
        """
        # 取消所有相关的邮件检查任务
        for request_id in self._get_conversation_requests(conversation_id):
            request_key = (conversation_id, request_id)
            if request_key in self._mail_check_tasks:
                self._mail_check_tasks[request_key].cancel()
                del self._mail_check_tasks[request_key]
                
        # 调用父类方法取消对话
        return await super().cancel_conversation(conversation_id)