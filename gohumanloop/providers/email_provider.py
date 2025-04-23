import os
import asyncio
import smtplib
from imapclient import IMAPClient
import email.mime.multipart
import email.mime.text
from email.header import decode_header
from email import message_from_bytes
from email.message import Message
import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from pydantic import SecretStr

from gohumanloop.core.interface import ( HumanLoopResult, HumanLoopStatus, HumanLoopType
)
from gohumanloop.providers.base import BaseProvider
from gohumanloop.utils import get_secret_from_env
logger = logging.getLogger(__name__)

class EmailProvider(BaseProvider):
    """Email-based human-in-the-loop provider implementation"""
    
    def __init__(
        self,
        name: str,
        smtp_server: str,
        smtp_port: int,
        imap_server: str,
        imap_port: int,
        username: Optional[str] = None,
        password: Optional[SecretStr]=None,
        sender_email: Optional[str] = None,
        check_interval: int = 60,
        config: Optional[Dict[str, Any]] = None
    ):
        """Initialize Email Provider
        
        Args:
            name: Provider name
            smtp_server: SMTP server address
            smtp_port: SMTP server port
            imap_server: IMAP server address
            imap_port: IMAP server port
            username: Email username
            password: Email password
            sender_email: Sender email address (if different from username)
            check_interval: Email check interval in seconds
            config: Additional configuration parameters
        """
        super().__init__(name, config)
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.imap_server = imap_server
        self.imap_port = imap_port

         # 优先从参数获取凭证，如果未提供则从环境变量获取
        self.username = username or os.environ.get("GOHUMANLOOP_EMAIL_USERNAME")
        if not self.username:
            raise ValueError(f"Email username not provided, please set it via parameter or environment variable GOHUMANLOOP_EMAIL_USERNAME")
            
        self.password = password or get_secret_from_env("GOHUMANLOOP_EMAIL_PASSWORD")
        if not self.password:
            raise ValueError(f"Email password not provided, please set it via parameter or environment variable GOHUMANLOOP_EMAIL_PASSWORD")

        self.sender_email = sender_email or self.username
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
        """Send email
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            body: Email body (plain text)
            html_body: Email body (HTML format, optional)
            reply_to: Reply email ID (optional)
            
        Returns:
            bool: Whether sending was successful
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
            logger.error(f"Failed to send email: {str(e)}", exc_info=True)
            return False
            
    def _send_email_sync(self, msg):
        """Synchronously send email (runs in executor)"""
        try:
            with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port) as server:
                server.login(self.username, self.password.get_secret_value())
                server.send_message(msg)
        except smtplib.SMTPException as e:
            logger.exception(f"SMTP error: {str(e)}")
            raise
        except Exception as e:
            logger.exception(f"Unknown error occurred while sending email: {str(e)}")
            raise
            
    async def _check_emails(self, conversation_id: str, request_id: str, recipient_email: str, subject: str):
        """Check email replies
        
        Args:
            conversation_id: Conversation ID
            request_id: Request ID 
            recipient_email: Recipient email address
            subject: Email subject
        """
        request_key = (conversation_id, request_id)
        
        while request_key in self._requests and self._requests[request_key]["status"] in [
            HumanLoopStatus.PENDING
        ]:
            try:
                # 使用异步方式检查邮件
                loop = asyncio.get_event_loop()
                email_msg = await loop.run_in_executor(
                    None,
                    self._fetch_emails_sync,
                    subject,
                    recipient_email
                )
                
     
                await self._process_email_response(conversation_id, request_id, email_msg)
            
                # 等待一段时间后再次检查
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Failed to check emails: {str(e)}", exc_info=True)
                if request_key in self._requests:
                    self._requests[request_key]["status"] = HumanLoopStatus.ERROR 
                    self._requests[request_key]["error"] = f"Failed to check emails: {str(e)}"
                break
                
    def _decode_email_header(self, header_value: str) -> str:
        """Parse email header information and handle potential encoding issues
        
        Args:
            header_value: Raw email header value
            
        Returns:
            str: Decoded email header value
        """
        decoded_parts = decode_header(header_value)
        result = ""
        for part, charset in decoded_parts:
            if isinstance(part, bytes):
                # 如果字符集未指定，默认使用utf-8
                charset = charset or "utf-8"
                result += part.decode(charset)
            else:
                result += str(part)
        return result
    
    def _fetch_emails_sync(self, subject: str, sender_email: Optional[str] = None) -> Any:
        """Synchronously fetch emails (runs in executor)
        
        Args:
            subject: Email subject
            sender_email: Sender email address (optional filter)
            
        Returns:
            List[email.message.Message]: List of matching emails
        """

        # 连接到IMAP服务器
        with IMAPClient(host=self.imap_server, port=self.imap_port ,ssl=True) as client:
            client.login(self.username, self.password.get_secret_value())
        
            # 发送 ID 命令，解决某些邮箱服务器的安全限制（如网易邮箱）
            try:
                client.id_({
                    "name": "GoHumanLoop",
                    "version": "1.0.0",
                    "vendor": "GoHumanLoop Client",
                    "contact": "baird0917@163.com"
                })
                logger.debug("IMAP ID command sent")
            except Exception as e:
                logger.warning(f"Failed to send IMAP ID command: {str(e)}")
            
            # 选择收件箱
            client.select_folder("INBOX", readonly=True)
             
            # 执行搜索
            messages = client.search("UNSEEN")
            
            if not messages:
                logger.warning(f"No unread emails found")
                return None
            
            # 获取邮件内容
            for uid, message_data in client.fetch(messages, "RFC822").items():
                email_message = message_from_bytes(message_data[b"RFC822"])
                
                # 使用通用方法解析发件人
                from_header = self._decode_email_header(email_message.get("From", ""))
                
                # 使用通用方法解析主题
                email_subject = self._decode_email_header(email_message.get("Subject", ""))
                
                # 检查是否匹配发件人和主题条件
                if (sender_email and sender_email not in from_header) or \
                (subject and subject not in email_subject):
                    continue
                return email_message
            return None
        
    async def _process_email_response(self, conversation_id: str, request_id: str, email_msg: Message):

        """Process email response
        
        Args:
            conversation_id: Conversation ID
            request_id: Request ID 
            email_msg: Email message object
        """
        if email_msg is None:
            return

        request_key = (conversation_id, request_id)
        if request_key not in self._requests:
            return
            
        # 提取邮件内容
        body = ""
        html_body = ""
        
        if email_msg.is_multipart():
            for part in email_msg.walk():
                content_type = part.get_content_type()
                charse_type = part.get_content_charset()
                content_disposition = str(part.get("Content-Disposition"))
                
                # 跳过附件
                if "attachment" in content_disposition:
                    continue
                    
                # 获取邮件内容
                payload = part.get_payload(decode=True)
                if payload is None:
                    continue
                    
                if content_type == "text/plain":
                    body = payload.decode(encoding=charse_type)
                elif content_type == "text/html":
                    html_body = payload.decode(encoding=charse_type)
        else:
            # 非多部分邮件
            charse_type = email_msg.get_content_charset()
            payload = email_msg.get_payload(decode=True)
            if payload: 
                body = payload.decode(encoding=charse_type)
        
        # 获取请求信息
        request_info = self._requests[request_key]
        loop_type = request_info.get("loop_type", HumanLoopType.CONVERSATION)
        responded_by  = self._decode_email_header(email_msg.get("From", "")) 
        # 解析响应内容
        parsed_response = {
            "text": body,
            "html": html_body,
            "subject": self._decode_email_header(email_msg.get("Subject", "")),
            "from":  responded_by,
            "date": self._decode_email_header(email_msg.get("Date", "")),
            "message_id": email_msg.get("Message-ID", "")
        }
        
        # 根据不同的循环类型解析回复
        if loop_type == HumanLoopType.APPROVAL:
            # 解析审批决定和理由
            decision = None
            reason = None
            
            for line in body.split('\n'):
                line = line.strip()
                if line.startswith("决定"):
                    decision_text = line[3:].strip().lower()
                    if "批准" in decision_text or "同意" in decision_text or "approve" in decision_text:
                        decision = "approved"
                        break
                    elif "拒绝" in decision_text or "否决" in decision_text or "reject" in decision_text:
                        decision = "rejected"
                    else:
                        decision = "rejected"
                        reason = "未提供有效的审批决定"
                elif line.startswith("理由"):
                    reason = line[3:].strip()
            
            parsed_response["decision"] = decision
            parsed_response["reason"] = reason
            
            
            # 设置状态
            if decision == "approved":
                status = HumanLoopStatus.APPROVED
            elif decision == "rejected":
                status = HumanLoopStatus.REJECTED
                
                
        elif loop_type == HumanLoopType.INFORMATION:
            # 解析提供的信息和备注
            information = None
            notes = None
            
            for line in body.split('\n'):
                line = line.strip()
                if line.startswith("信息"):
                    information = line[3:].strip()
                elif line.startswith("备注"):
                    notes = line[3:].strip()
            
            parsed_response["information"] = information
            parsed_response["notes"] = notes
            status = HumanLoopStatus.COMPLETED
            
        elif loop_type == HumanLoopType.CONVERSATION:
            # 检查是否结束对话
            if "[结束对话]" in body:
                parsed_response["conversation_ended"] = True
                status = HumanLoopStatus.COMPLETED
            else:
                status = HumanLoopStatus.INPROGRESS
        else:
            status = HumanLoopStatus.COMPLETED
            
        # 更新请求状态
        self._requests[request_key].update({
            "status": status,
            "response": parsed_response,
            "responded_by": responded_by,
            "responded_at": datetime.now().isoformat()
        })
        
        # 取消超时任务
        if request_key in self._timeout_tasks:
            self._timeout_tasks[request_key].cancel()
            del self._timeout_tasks[request_key]
            
    def _format_email_body(self, body: str, loop_type: HumanLoopType) -> Tuple[str, str]:
        """Format email body
        
        Args:
            body: Email body content
            loop_type: Loop type
            
        Returns:
            Tuple[str, str]: (Plain text body, HTML body)
        """
        # 构建纯文本正文
        text_body = body
        
        # 根据不同的循环类型添加回复指导
        if loop_type == HumanLoopType.APPROVAL:
            text_body += "\n\n请按以下格式回复：\n"
            text_body += "决定：[批准/拒绝]\n"
            text_body += "理由：[您的理由]\n"
        elif loop_type == HumanLoopType.INFORMATION:
            text_body += "\n\n请按以下格式回复：\n"
            text_body += "信息：[您提供的信息]\n"
            text_body += "备注：[可选备注]\n"
        elif loop_type == HumanLoopType.CONVERSATION:
            text_body += "\n\n请直接回复您的内容。如需结束对话，请在回复中包含\"[结束对话]\"。\n"
        
        # 构建HTML正文
        html_body = ["<html><body>"]
        
        # 将纯文本内容按行分割并转换为HTML段落
        content_lines = []
        instruction_lines = []
        
        # 分离内容和指导说明
        lines = text_body.split('\n')
        instruction_start = -1
        
        for i, line in enumerate(lines):
            if line.strip() == "请按以下格式回复：" or line.strip() == "请直接回复您的内容。如需结束对话，请在回复中包含\"[结束对话]\"。":
                instruction_start = i
                break
        
        if instruction_start > -1:
            content_lines = lines[:instruction_start]
            instruction_lines = lines[instruction_start:]
        else:
            content_lines = lines
        
        # 添加主要内容
        for line in content_lines:
            if line.strip():
                html_body.append(f"<p>{line}</p>")
        
        # 添加回复指导（使用不同的样式）
        if instruction_lines:
            html_body.append("<hr>")
            html_body.append("<div style='background-color: #f5f5f5; padding: 10px; border-left: 4px solid #007bff;'>")
            
            if loop_type == HumanLoopType.APPROVAL:
                html_body.append("<p><strong>请按以下格式回复：</strong></p>")
                html_body.append("<pre style='background-color: #ffffff; padding: 8px; border: 1px solid #ddd;'>")
                html_body.append("决定：[批准/拒绝]<br>")
                html_body.append("理由：[您的理由]")
                html_body.append("</pre>")
            elif loop_type == HumanLoopType.INFORMATION:
                html_body.append("<p><strong>请按以下格式回复：</strong></p>")
                html_body.append("<pre style='background-color: #ffffff; padding: 8px; border: 1px solid #ddd;'>")
                html_body.append("信息：[您提供的信息]<br>")
                html_body.append("备注：[可选备注]")
                html_body.append("</pre>")
            elif loop_type == HumanLoopType.CONVERSATION:
                html_body.append("<p><strong>请直接回复您的内容。如需结束对话，请在回复中包含\"[结束对话]\"。</strong></p>")
            
            html_body.append("</div>")
        
        html_body.append("</body></html>")
        
        return text_body, "\n".join(html_body)
        
    async def request_humanloop(
        self,
        task_id: str,
        conversation_id: str,
        loop_type: HumanLoopType,
        context: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None
    ) -> HumanLoopResult:
        """Request human-in-the-loop interaction
        
        Args:
            task_id: Task identifier
            conversation_id: Conversation ID for multi-turn dialogues
            loop_type: Type of loop interaction
            context: Context information provided to human
            metadata: Additional metadata
            timeout: Request timeout in seconds
            
        Returns:
            HumanLoopResult: Result object containing request ID and initial status
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
                error="Recipient email address is missing"
            )
            
        # 生成邮件主题
        subject_prefix = metadata.get("subject_prefix", f"[{self.name}]")
        subject = metadata.get("subject", f"{subject_prefix} Task {task_id}")
        
        # 如果是继续对话，使用相同的主题
        if conversation_id in self._conversations:
            conversation_info = self._get_conversation(conversation_id)
            if conversation_info:
                last_request_id = conversation_info.get("last_request_id")
                last_request_key = (conversation_id, last_request_id)
                if last_request_key in self._requests:
                    last_metadata = self._requests[last_request_key].get("metadata", {})
                    if "subject" in last_metadata:
                        subject = last_metadata["subject"]

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

        # 构建邮件内容
        prompt = self.build_prompt(
            task_id=task_id,
            conversation_id=conversation_id,
            request_id=request_id,
            loop_type=loop_type,
            created_at=datetime.now().isoformat(),
            context=context,
            metadata=metadata
        )

        body, html_body = self._format_email_body(prompt, loop_type)
        
       
        
        # 发送邮件
        success = await self._send_email(
            to_email=recipient_email,
            subject=subject,
            body=body,
            html_body=html_body
        )
        
        if not success:
            # Update request status to error
            request_key = (conversation_id, request_id)
            if request_key in self._requests:
                self._requests[request_key]["status"] = HumanLoopStatus.ERROR
                self._requests[request_key]["error"] = "Failed to send email"
                
            return HumanLoopResult(
                conversation_id=conversation_id,
                request_id=request_id,
                loop_type=loop_type,
                status=HumanLoopStatus.ERROR,
                error="Failed to send email"
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
        """Check request status
        
        Args:
            conversation_id: Conversation identifier
            request_id: Request identifier
            
        Returns:
            HumanLoopResult: Result object containing current status
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
            status=request_info.get("status", HumanLoopStatus.PENDING),
            response=request_info.get("response", {}),
            feedback=request_info.get("feedback", {}),
            responded_by=request_info.get("responded_by", None),
            responded_at=request_info.get("responded_at", None),
            error=request_info.get("error", None)
        )
        
        return result
        
    async def continue_humanloop(
        self,
        conversation_id: str,
        context: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> HumanLoopResult:
        """Continue human-in-the-loop interaction
        
        Args:
            conversation_id: Conversation ID for multi-turn dialogues
            context: Context information provided to human
            metadata: Additional metadata
            timeout: Request timeout in seconds
            
        Returns:
            HumanLoopResult: Result object containing request ID and status
        """
        """Continue human-in-the-loop interaction for multi-turn dialogues
        
        Args:
            conversation_id: Conversation ID
            context: Context information provided to human
            metadata: Additional metadata 
            timeout: Request timeout in seconds
            
        Returns:
            HumanLoopResult: Result object containing request ID and status
        """
        metadata = metadata or {}

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
        
        # 生成新的请求ID
        request_id = self._generate_request_id()
        
        # 获取任务ID
        task_id = conversation_info.get("task_id", "unknown_task")
         # 获取收件人邮箱
        recipient_email = metadata.get("recipient_email")
        if not recipient_email:
            return HumanLoopResult(
                conversation_id=conversation_id,
                request_id=request_id,
                loop_type=HumanLoopType.CONVERSATION,
                status=HumanLoopStatus.ERROR,
                error="Recipient email address is missing"
            )

     
        # 继续对话，使用相同的主题
        if conversation_id in self._conversations:
            conversation_info = self._get_conversation(conversation_id)
            if conversation_info:
                last_request_id = conversation_info.get("last_request_id")
                last_request_key = (conversation_id, last_request_id)
                if last_request_key in self._requests:
                    last_metadata = self._requests[last_request_key].get("metadata", {})
                    if "subject" in last_metadata:
                        subject = last_metadata["subject"]

        # 存储请求信息
        self._store_request(
            conversation_id=conversation_id,
            request_id=request_id,
            task_id=task_id,
            loop_type=HumanLoopType.CONVERSATION,  # 继续对话默认为对话类型
            context=context,
            metadata=metadata or {},
            timeout=timeout
        )

        # 构建邮件内容
        prompt = self.build_prompt(
            task_id=task_id,
            conversation_id=conversation_id,
            request_id=request_id,
            loop_type=HumanLoopType.CONVERSATION,
            created_at=datetime.now().isoformat(),
            context=context,
            metadata=metadata,
            color=False
        )

        body, html_body = self._format_email_body(prompt, HumanLoopType.CONVERSATION)

        # 发送邮件
        success = await self._send_email(
            to_email=recipient_email,
            subject=subject,
            body=body,
            html_body=html_body
        )
        
        if not success:
            # Update request status to error
            request_key = (conversation_id, request_id)
            if request_key in self._requests:
                self._requests[request_key]["status"] = HumanLoopStatus.ERROR
                self._requests[request_key]["error"] = "Failed to send email"
                
            return HumanLoopResult(
                conversation_id=conversation_id,
                request_id=request_id,
                loop_type=HumanLoopType.CONVERSATION,
                status=HumanLoopStatus.ERROR,
                error="Failed to send email"
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
            loop_type=HumanLoopType.CONVERSATION,
            status=HumanLoopStatus.PENDING
        )

    async def cancel_request(
        self,
        conversation_id: str,
        request_id: str
    ) -> bool:
        """Cancel human-in-the-loop request
        
        Args:
            conversation_id: Conversation identifier for multi-turn dialogues
            request_id: Request identifier for specific interaction request
            
        Return:
            bool: Whether cancellation was successful, True indicates successful cancellation,
                 False indicates cancellation failed
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
        """Cancel the entire conversation
        
        Args:
            conversation_id: Conversation identifier
            
        Returns:
            bool: Whether cancellation was successful
        """
        # 取消所有相关的邮件检查任务
        for request_id in self._get_conversation_requests(conversation_id):
            request_key = (conversation_id, request_id)
            if request_key in self._mail_check_tasks:
                self._mail_check_tasks[request_key].cancel()
                del self._mail_check_tasks[request_key]
                
        # 调用父类方法取消对话
        return await super().cancel_conversation(conversation_id)