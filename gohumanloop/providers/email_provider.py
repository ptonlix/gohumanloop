import os
import re
import asyncio
import smtplib
from imapclient import IMAPClient  # type: ignore
import email.mime.multipart
import email.mime.text
from email.header import decode_header
from email import message_from_bytes
from email.message import Message
import logging
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
from pydantic import SecretStr
from concurrent.futures import ThreadPoolExecutor, Future

from gohumanloop.core.interface import HumanLoopResult, HumanLoopStatus, HumanLoopType
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
        password: Optional[SecretStr] = None,
        sender_email: Optional[str] = None,
        check_interval: int = 60,
        language: str = "zh",
        config: Optional[Dict[str, Any]] = None,
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
            language: Language for templates and messages ("zh" for Chinese, "en" for English)
            config: Additional configuration parameters
        """
        super().__init__(name, config)
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.imap_server = imap_server
        self.imap_port = imap_port
        self.language = language  # 保存语言设置

        # 优先从参数获取凭证，如果未提供则从环境变量获取
        self.username = username or os.environ.get("GOHUMANLOOP_EMAIL_USERNAME")
        if not self.username:
            raise ValueError(
                "Email username not provided, please set it via parameter or environment variable GOHUMANLOOP_EMAIL_USERNAME"
            )

        self.password = password or get_secret_from_env("GOHUMANLOOP_EMAIL_PASSWORD")
        if not self.password:
            raise ValueError(
                "Email password not provided, please set it via parameter or environment variable GOHUMANLOOP_EMAIL_PASSWORD"
            )

        self.sender_email = sender_email or self.username
        self.check_interval = check_interval

        # 存储邮件主题与请求ID的映射关系
        self._subject_to_request: Dict[str, Tuple[str, str]] = {}
        # 存储正在运行的邮件检查任务
        self._mail_check_tasks: Dict[Tuple[str, str], Future] = {}
        # 存储邮件会话ID与对话ID的映射
        self._thread_to_conversation: Dict[str, str] = {}

        self._init_language_templates()

        # Create thread pool for background service execution
        self._executor = ThreadPoolExecutor(max_workers=10)

    def __del__(self) -> None:
        """析构函数，确保线程池被正确关闭"""
        self._executor.shutdown(wait=False)

        # 取消所有邮件检查任务
        for task_key, future in list(self._mail_check_tasks.items()):
            future.cancel()
        self._mail_check_tasks.clear()

    def _init_language_templates(self) -> None:
        """初始化不同语言的模板和关键词"""
        if self.language == "zh":
            # 中文关键词和模板
            self.approve_keywords = {"批准", "同意", "approve"}
            self.reject_keywords = {"拒绝", "否决", "reject"}
            self.templates = {
                "approval_instruction": "请按以下格式回复：",
                "content_start_mark": "===== 请保留此行作为内容开始标记 =====",
                "content_end_mark": "===== 请保留此行作为内容结束标记 =====",
                "decision_prefix": "决定：",
                "reason_prefix": "理由：",
                "information_prefix": "信息：",
                "conversation_instruction": '请直接回复您的内容。如需结束对话，请在回复中包含"[结束对话]"。',
                "conversation_end_mark": "[结束对话]",
                "input_placeholder": "[请在此处输入您的回复内容]",
                "approve_template_title": "批准模板：",
                "reject_template_title": "拒绝模板：",
                "info_template_title": "信息提供模板：",
                "template_instruction": "请选择一个模板，复制到您的回复中，替换方括号内的内容后发送。请保留标记行，这将帮助系统准确识别您的回复。",
                "info_template_instruction": "请复制上面的模板到您的回复中，替换方括号内的内容后发送。请保留标记行，这将帮助系统准确识别您的回复。",
                "footer": "由 GoHumanLoop 提供支持 - Perfecting AI workflows with human intelligence",
                "continue_conversation_template": "继续对话模板：",
                "end_conversation_template": "结束对话模板：",
                "invalid_decision": "未提供有效的审批决定",
                "powered_by": "由 GoHumanLoop 提供支持",
            }
        else:
            # 英文关键词和模板
            self.approve_keywords = {"approve", "approved", "accept", "yes"}
            self.reject_keywords = {"reject", "rejected", "deny", "no"}
            self.templates = {
                "approval_instruction": "Please reply in the following format:",
                "content_start_mark": "===== PLEASE KEEP THIS LINE AS CONTENT START MARKER =====",
                "content_end_mark": "===== PLEASE KEEP THIS LINE AS CONTENT END MARKER =====",
                "decision_prefix": "Decision: ",
                "reason_prefix": "Reason: ",
                "information_prefix": "Information: ",
                "conversation_instruction": 'Please reply directly with your content. If you want to end the conversation, include "[END CONVERSATION]" in your reply.',
                "conversation_end_mark": "[END CONVERSATION]",
                "input_placeholder": "[Please enter your reply here]",
                "approve_template_title": "Approval Template:",
                "reject_template_title": "Rejection Template:",
                "info_template_title": "Information Template:",
                "template_instruction": "Please select a template, copy it to your reply, replace the content in brackets, and send. Please keep the marker lines as they help the system accurately identify your reply.",
                "info_template_instruction": "Please copy the template above to your reply, replace the content in brackets, and send. Please keep the marker lines as they help the system accurately identify your reply.",
                "footer": "Powered by GoHumanLoop - Perfecting AI workflows with human intelligence",
                "continue_conversation_template": "Continue Conversation Template:",
                "end_conversation_template": "End Conversation Template:",
                "invalid_decision": "No valid approval decision provided",
                "powered_by": "Powered by GoHumanLoop",
            }

    async def _async_send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        reply_to: Optional[str] = None,
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
            msg = email.mime.multipart.MIMEMultipart("alternative")
            msg["From"] = self.sender_email
            msg["To"] = to_email
            msg["Subject"] = subject

            # 添加纯文本内容
            msg.attach(email.mime.text.MIMEText(body, "plain"))

            # 如果提供了HTML内容，也添加HTML版本
            if html_body:
                msg.attach(email.mime.text.MIMEText(html_body, "html"))

            # 如果是回复邮件，添加相关邮件头
            if reply_to:
                msg["In-Reply-To"] = reply_to
                msg["References"] = reply_to

            # 使用异步方式发送邮件
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._send_email_sync, msg)
            return True
        except Exception as e:
            logger.error(f"Failed to send email: {str(e)}", exc_info=True)
            return False

    def _send_email_sync(self, msg: email.mime.multipart.MIMEMultipart) -> None:
        """Synchronously send email (runs in executor)"""
        try:
            with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port) as server:
                if self.username is None:
                    raise ValueError("Username is not set")
                if self.password is None:
                    raise ValueError("Password is not set")
                server.login(self.username, self.password.get_secret_value())
                server.send_message(msg)
        except smtplib.SMTPException as e:
            logger.exception(f"SMTP error: {str(e)}")
            raise
        except Exception as e:
            logger.exception(f"Unknown error occurred while sending email: {str(e)}")
            raise

    async def _async_check_emails_with_timeout(
        self,
        conversation_id: str,
        request_id: str,
        recipient_email: str,
        subject: str,
        timeout: Optional[int],
    ) -> None:
        """Check email replies with timeout functionality

        Args:
            conversation_id: Conversation ID to identify a complete dialogue session
            request_id: Request ID to identify a specific request
            recipient_email: Recipient's email address
            subject: Email subject line
            timeout: Timeout duration in seconds, no timeout if None
        """

        try:
            if timeout:
                # 使用 wait_for 设置超时
                await asyncio.wait_for(
                    self._async_check_emails(
                        conversation_id, request_id, recipient_email, subject
                    ),
                    timeout=timeout,
                )
            else:
                # 无超时限制
                await self._async_check_emails(
                    conversation_id, request_id, recipient_email, subject
                )

        except asyncio.TimeoutError:
            # 超时处理
            request_info = self._get_request(conversation_id, request_id)
            if request_info and request_info.get("status") == HumanLoopStatus.PENDING:
                request_info["status"] = HumanLoopStatus.EXPIRED
                request_info["error"] = "Request timed out"
                logger.info(
                    f"\nRequest {request_id} has timed out after {timeout} seconds"
                )

    async def _async_check_emails(
        self, conversation_id: str, request_id: str, recipient_email: str, subject: str
    ) -> None:
        """Check email replies

        Args:
            conversation_id: Conversation ID
            request_id: Request ID
            recipient_email: Recipient email address
            subject: Email subject
        """
        request_key = (conversation_id, request_id)

        while request_key in self._requests and self._requests[request_key][
            "status"
        ] in [HumanLoopStatus.PENDING]:
            try:
                # 使用异步方式检查邮件
                loop = asyncio.get_event_loop()
                email_msg = await loop.run_in_executor(
                    None, self._fetch_emails_sync, subject, recipient_email
                )

                await self._process_email_response(
                    conversation_id, request_id, email_msg
                )

                # 等待一段时间后再次检查
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Failed to check emails: {str(e)}", exc_info=True)
                self._update_request_status_error(
                    conversation_id, request_id, f"Failed to check emails: {str(e)}"
                )
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

    def _fetch_emails_sync(
        self, subject: str, sender_email: Optional[str] = None
    ) -> Any:
        """Synchronously fetch emails (runs in executor)

        Args:
            subject: Email subject
            sender_email: Sender email address (optional filter)

        Returns:
            List[email.message.Message]: List of matching emails
        """

        # 连接到IMAP服务器
        with IMAPClient(host=self.imap_server, port=self.imap_port, ssl=True) as client:
            if self.username is None:
                raise ValueError("Username is not set")
            if self.password is None:
                raise ValueError("Password is not set")
            client.login(self.username, self.password.get_secret_value())

            # 发送 ID 命令，解决某些邮箱服务器的安全限制（如网易邮箱）
            try:
                client.id_(
                    {
                        "name": "GoHumanLoop",
                        "version": "1.0.0",
                        "vendor": "GoHumanLoop Client",
                        "contact": "baird0917@163.com",
                    }
                )
                logger.debug("IMAP ID command sent")
            except Exception as e:
                logger.warning(f"Failed to send IMAP ID command: {str(e)}")

            # 选择收件箱
            client.select_folder("INBOX")

            # 执行搜索
            messages = client.search("UNSEEN")

            if not messages:
                logger.warning("No unread emails found")
                return None

            # 获取邮件内容
            for uid, message_data in client.fetch(messages, "RFC822").items():
                email_message = message_from_bytes(message_data[b"RFC822"])

                # 使用通用方法解析发件人
                from_header = self._decode_email_header(email_message.get("From", ""))

                # 使用通用方法解析主题
                email_subject = self._decode_email_header(
                    email_message.get("Subject", "")
                )

                # 检查是否匹配发件人和主题条件
                if (sender_email and sender_email not in from_header) or (
                    subject and subject not in email_subject
                ):
                    continue

                # 将邮件标记为已读
                client.set_flags(uid, [b"\\Seen"])
                return email_message
            return None

    async def _process_email_response(
        self, conversation_id: str, request_id: str, email_msg: Message
    ) -> None:
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
                charse_type = part.get_content_charset() or "utf-8"
                content_disposition = str(part.get("Content-Disposition"))

                # 跳过附件
                if "attachment" in content_disposition:
                    continue

                # 获取邮件内容
                payload = part.get_payload(decode=True)
                if payload is None:
                    continue

                if isinstance(payload, bytes):
                    if content_type == "text/plain":
                        # 如果字符集未指定，使用默认的utf-8
                        body = payload.decode(encoding=charse_type)
                    elif content_type == "text/html":
                        html_body = payload.decode(encoding=charse_type)
        else:
            # 非多部分邮件
            charse_type = email_msg.get_content_charset() or "utf-8"
            payload = email_msg.get_payload(decode=True)
            if isinstance(payload, bytes):
                body = payload.decode(encoding=charse_type)

        # 获取请求信息
        request_info = self._requests[request_key]
        loop_type = request_info.get("loop_type", HumanLoopType.CONVERSATION)
        responded_by = self._decode_email_header(email_msg.get("From", ""))

        # 解析响应内容
        parsed_response = {
            "text": body,
            "html": html_body,
            "subject": self._decode_email_header(email_msg.get("Subject", "")),
            "from": responded_by,
            "date": self._decode_email_header(email_msg.get("Date", "")),
            "message_id": email_msg.get("Message-ID", ""),
        }

        # 提取用户的实际回复内容
        user_content = self._extract_user_reply_content(body)
        logger.debug(f"user_content:\n {user_content}")
        # 根据不同的循环类型解析回复
        if loop_type == HumanLoopType.APPROVAL:
            # 解析审批决定和理由
            decision = ""
            reason = ""

            # 使用语言相关的关键词
            approve_keywords = self.approve_keywords
            reject_keywords = self.reject_keywords
            decision_prefix = self.templates["decision_prefix"]

            # 遍历每行内容寻找决定信息
            if user_content:
                for line in map(str.strip, user_content.split("\n")):
                    if not line.startswith(decision_prefix):
                        continue

                    decision_text = line[len(decision_prefix) :].strip().lower()

                    # 判断决定类型
                    if any(keyword in decision_text for keyword in approve_keywords):
                        decision = "approved"
                    elif any(keyword in decision_text for keyword in reject_keywords):
                        decision = "rejected"
                    else:
                        decision = "rejected"
                        reason = self.templates["invalid_decision"]
                        break

                    # 提取理由
                    reason_prefix = self.templates["reason_prefix"]
                    if reason_prefix in line:
                        reason = line[
                            line.find(reason_prefix) + len(reason_prefix) :
                        ].strip()
                    break

            parsed_response["decision"] = decision
            parsed_response["reason"] = reason

            # 设置状态
            if decision == "approved":
                status = HumanLoopStatus.APPROVED
            elif decision == "rejected":
                status = HumanLoopStatus.REJECTED

        elif loop_type == HumanLoopType.INFORMATION:
            # 解析提供的信息和备注
            information = ""
            information_prefix = self.templates["information_prefix"]

            if user_content:
                for line in user_content.split("\n"):
                    line = line.strip()
                    if line.startswith(information_prefix):
                        information = line[len(information_prefix) :].strip()
                        break

            parsed_response["information"] = information
            status = HumanLoopStatus.COMPLETED

        elif loop_type == HumanLoopType.CONVERSATION:
            conversation_end_mark = self.templates["conversation_end_mark"]

            # 检查用户的实际回复内容中是否包含结束对话的标记
            if user_content and conversation_end_mark in user_content:
                parsed_response["user_content"] = user_content
                status = HumanLoopStatus.COMPLETED
            else:
                parsed_response["user_content"] = user_content or ""
                status = HumanLoopStatus.INPROGRESS
        else:
            status = HumanLoopStatus.COMPLETED

        # 更新请求状态
        self._requests[request_key].update(
            {
                "status": status,
                "response": parsed_response,
                "responded_by": responded_by,
                "responded_at": datetime.now().isoformat(),
            }
        )

    def _format_email_body(
        self, body: str, loop_type: HumanLoopType, subject: str
    ) -> Tuple[str, str]:
        """Format email body

        Args:
            body: Email body content
            loop_type: Loop type
            conversation_id: Conversation ID (optional)
            request_id: Request ID (optional)

        Returns:
            Tuple[str, str]: (Plain text body, HTML body)
        """

        # 获取模板文本
        templates = self.templates

        # 构建纯文本正文
        text_body = body

        # 根据不同的循环类型添加回复指导
        if loop_type == HumanLoopType.APPROVAL:
            text_body += f"\n\n{templates['approval_instruction']}\n"
            text_body += f"{templates['content_start_mark']}\n"
            text_body += f"{templates['decision_prefix']}[{'/'.join(self.approve_keywords)}|{'/'.join(self.reject_keywords)}]\n"
            text_body += f"{templates['reason_prefix']}[Your reason]\n"
            text_body += f"{templates['content_end_mark']}\n"
        elif loop_type == HumanLoopType.INFORMATION:
            text_body += f"\n\n{templates['approval_instruction']}\n"
            text_body += f"{templates['content_start_mark']}\n"
            text_body += f"{templates['information_prefix']}[Your information]\n"
            text_body += f"{templates['content_end_mark']}\n"
        elif loop_type == HumanLoopType.CONVERSATION:
            text_body += f"\n\n{templates['conversation_instruction']}\n"
            text_body += f"{templates['content_start_mark']}\n"
            text_body += f"{templates['input_placeholder']}\n"
            text_body += f"{templates['content_end_mark']}\n"

        # 添加纯文本版本的宣传标识
        text_body += f"\n\n---\n{templates['footer']}\n"

        # 构建HTML正文
        html_body = ["<html><body>"]

        # 将纯文本内容按行分割并转换为HTML段落
        content_lines = []
        instruction_lines = []

        # 分离内容和指导说明
        lines = text_body.split("\n")
        instruction_start = -1

        for i, line in enumerate(lines):
            if (
                line.strip() == templates["approval_instruction"]
                or line.strip() == templates["conversation_instruction"]
            ):
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
            html_body.append(
                "<div style='background-color: #f5f5f5; padding: 10px; border-left: 4px solid #007bff;'>"
            )

            if loop_type == HumanLoopType.APPROVAL:
                html_body.append(
                    f"<p><strong>{templates['approval_instruction']}</strong></p>"
                )
                # 添加预格式化回复模板
                html_body.append(
                    f"""
<div style="margin-top: 15px;">
    <div style="background-color: #f8f9fa; padding: 15px; border: 1px solid #ddd; border-radius: 5px;">
        <p style="margin: 0 0 10px 0; font-weight: bold;">{templates['approve_template_title']}</p>
        <pre style="background-color: #ffffff; padding: 10px; border: 1px solid #eee; margin: 0 0 15px 0;">
{templates['content_start_mark']}
{templates['decision_prefix']}{list(self.approve_keywords)[0]}
{templates['reason_prefix']}[Your reason]
{templates['content_end_mark']}</pre>

        <p style="margin: 0 0 10px 0; font-weight: bold;">{templates['reject_template_title']}</p>
        <pre style="background-color: #ffffff; padding: 10px; border: 1px solid #eee; margin: 0;">
{templates['content_start_mark']}
{templates['decision_prefix']}{list(self.reject_keywords)[0]}
{templates['reason_prefix']}[Your reason]
{templates['content_end_mark']}</pre>
    </div>
    <p style="margin-top: 10px; font-size: 12px; color: #666;">
        {templates['template_instruction']}
    </p>
</div>
"""
                )
            elif loop_type == HumanLoopType.INFORMATION:
                html_body.append(
                    f"<p><strong>{templates['approval_instruction']}</strong></p>"
                )
                html_body.append(
                    f"""
<div style="margin-top: 15px;">
    <div style="background-color: #f8f9fa; padding: 15px; border: 1px solid #ddd; border-radius: 5px;">
        <p style="margin: 0 0 10px 0; font-weight: bold;">{templates['info_template_title']}</p>
        <pre style="background-color: #ffffff; padding: 10px; border: 1px solid #eee; margin: 0;">
{templates['content_start_mark']}
{templates['information_prefix']}[Your information]
{templates['content_end_mark']}</pre>
    </div>
    <p style="margin-top: 10px; font-size: 12px; color: #666;">
        {templates['info_template_instruction']}
    </p>
</div>
"""
                )
            elif loop_type == HumanLoopType.CONVERSATION:
                # 使用模板变量替换硬编码的中文
                html_body.append(
                    f"<p><strong>{templates['conversation_instruction']}</strong></p>"
                )

                # 添加预格式化回复模板
                html_body.append(
                    f"""
<div style="margin-top: 15px;">
    <div style="background-color: #f8f9fa; padding: 15px; border: 1px solid #ddd; border-radius: 5px;">
        <p style="margin: 0 0 10px 0; font-weight: bold;">{templates['continue_conversation_template']}</p>
        <pre style="background-color: #ffffff; padding: 10px; border: 1px solid #eee; margin: 0 0 15px 0;">
{templates['content_start_mark']}
{templates['input_placeholder']}
{templates['content_end_mark']}</pre>
        <p style="margin: 0 0 10px 0; font-weight: bold;">{templates['end_conversation_template']}</p>
        <pre style="background-color: #ffffff; padding: 10px; border: 1px solid #eee; margin: 0;">
{templates['content_start_mark']}
{templates['input_placeholder']}
{templates['conversation_end_mark']}
{templates['content_end_mark']}</pre>
    </div>
    <p style="margin-top: 10px; font-size: 12px; color: #666;">
        {templates['template_instruction']}
    </p>
</div>
"""
                )

            html_body.append("</div>")

        # 添加 GoHumanLoop 宣传标识
        html_body.append("<hr style='margin-top: 20px; margin-bottom: 10px;'>")
        html_body.append(
            "<div style='text-align: center; color: #666; font-size: 12px; margin-bottom: 10px;'>"
        )
        html_body.append(
            f"<p>{'由 ' if self.language == 'zh' else 'Powered by '}<strong style='color: #007bff;'><a href=\"https://github.com/ptonlix/gohumanloop\" style=\"color: #007bff; text-decoration: none;\">GoHumanLoop</a></strong>{' 提供支持' if self.language == 'zh' else ''}</p>"
        )
        html_body.append(
            f"<p style='font-style: italic;'>{templates['footer'].split(' - ')[1]}</p>"
        )
        html_body.append("</div>")

        return text_body, "\n".join(html_body)

    async def async_request_humanloop(
        self,
        task_id: str,
        conversation_id: str,
        loop_type: HumanLoopType,
        context: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
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

        # 生成邮件主题
        subject_prefix = metadata.get("subject_prefix", f"[{self.name}]")
        subject = metadata.get("subject", f"{subject_prefix} Task {task_id}")

        # 存储请求信息
        self._store_request(
            conversation_id=conversation_id,
            request_id=request_id,
            task_id=task_id,
            loop_type=loop_type,
            context=context,
            metadata={
                **metadata,
                "subject": subject,
                "recipient_email": recipient_email,
            },
            timeout=timeout,
        )

        if not recipient_email:
            self._update_request_status_error(
                conversation_id, request_id, "Recipient email address is missing"
            )
            return HumanLoopResult(
                conversation_id=conversation_id,
                request_id=request_id,
                loop_type=loop_type,
                status=HumanLoopStatus.ERROR,
                error="Recipient email address is missing",
            )

        # 构建邮件内容
        prompt = self.build_prompt(
            task_id=task_id,
            conversation_id=conversation_id,
            request_id=request_id,
            loop_type=loop_type,
            created_at=datetime.now().isoformat(),
            context=context,
            metadata=metadata,
            color=False,
        )

        body, html_body = self._format_email_body(prompt, loop_type, subject)

        # 发送邮件
        success = await self._async_send_email(
            to_email=recipient_email, subject=subject, body=body, html_body=html_body
        )

        if not success:
            # Update request status to error
            self._update_request_status_error(
                conversation_id, request_id, "Failed to send email"
            )

            return HumanLoopResult(
                conversation_id=conversation_id,
                request_id=request_id,
                loop_type=loop_type,
                status=HumanLoopStatus.ERROR,
                error="Failed to send email",
            )
        # 存储主题与请求的映射关系
        self._subject_to_request[subject] = (conversation_id, request_id)

        # 创建邮件检查任务
        # 使用线程池执行邮件检查任务，而不是使用asyncio.create_task
        self._mail_check_tasks[(conversation_id, request_id)] = self._executor.submit(
            self._run_email_check_task,
            conversation_id,
            request_id,
            recipient_email,
            subject,
            timeout,
        )

        return HumanLoopResult(
            conversation_id=conversation_id,
            request_id=request_id,
            loop_type=loop_type,
            status=HumanLoopStatus.PENDING,
        )

    def _run_email_check_task(
        self,
        conversation_id: str,
        request_id: str,
        recipient_email: str,
        subject: str,
        timeout: Optional[int],
    ) -> None:
        """Run email check task in thread

        Args:
            conversation_id: Conversation ID
            request_id: Request ID
            recipient_email: Recipient email address
            subject: Email subject
        """
        # Create new event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # Run email check in new event loop
            loop.run_until_complete(
                self._async_check_emails_with_timeout(
                    conversation_id, request_id, recipient_email, subject, timeout
                )
            )
        except Exception as e:
            logger.error(f"Email check task error: {str(e)}", exc_info=True)
            # Update request status to error
            self._update_request_status_error(
                conversation_id, request_id, f"Email check task error: {str(e)}"
            )
        finally:
            # Close event loop
            loop.close()
            # Remove from task dictionary
            if (conversation_id, request_id) in self._mail_check_tasks:
                del self._mail_check_tasks[(conversation_id, request_id)]

    async def async_check_request_status(
        self, conversation_id: str, request_id: str
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
                error=f"Request '{request_id}' not found in conversation '{conversation_id}'",
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
            error=request_info.get("error", None),
        )

        return result

    async def async_continue_humanloop(
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
                error=f"Conversation '{conversation_id}' not found",
            )

        # 生成新的请求ID
        request_id = self._generate_request_id()

        # 获取任务ID
        task_id = conversation_info.get("task_id", "unknown_task")

        # 存储请求信息
        self._store_request(
            conversation_id=conversation_id,
            request_id=request_id,
            task_id=task_id,
            loop_type=HumanLoopType.CONVERSATION,  # 继续对话默认为对话类型
            context=context,
            metadata=metadata or {},
            timeout=timeout,
        )

        # 获取收件人邮箱
        recipient_email = metadata.get("recipient_email")
        if not recipient_email:
            self._update_request_status_error(
                conversation_id, request_id, "Recipient email address is missing"
            )
            return HumanLoopResult(
                conversation_id=conversation_id,
                request_id=request_id,
                loop_type=HumanLoopType.CONVERSATION,
                status=HumanLoopStatus.ERROR,
                error="Recipient email address is missing",
            )

        # 继续对话，使用相同的主题
        if conversation_id in self._conversations:
            conversation_info = self._get_conversation(conversation_id)
            if conversation_info:
                latest_request_id = conversation_info.get("latest_request_id") or ""
                last_request_key = (conversation_id, latest_request_id)
                if last_request_key in self._requests:
                    last_metadata = self._requests[last_request_key].get("metadata", {})
                    if "subject" in last_metadata:
                        subject = last_metadata["subject"]
                        metadata["subject"] = subject  # 保持相同主题

        # 构建邮件内容
        prompt = self.build_prompt(
            task_id=task_id,
            conversation_id=conversation_id,
            request_id=request_id,
            loop_type=HumanLoopType.CONVERSATION,
            created_at=datetime.now().isoformat(),
            context=context,
            metadata=metadata,
            color=False,
        )

        body, html_body = self._format_email_body(
            prompt, HumanLoopType.CONVERSATION, subject
        )

        # 发送邮件
        success = await self._async_send_email(
            to_email=recipient_email, subject=subject, body=body, html_body=html_body
        )

        if not success:
            # Update request status to error
            self._update_request_status_error(
                conversation_id, request_id, "Failed to send email"
            )

            return HumanLoopResult(
                conversation_id=conversation_id,
                request_id=request_id,
                loop_type=HumanLoopType.CONVERSATION,
                status=HumanLoopStatus.ERROR,
                error="Failed to send email",
            )

        # 存储主题与请求的映射关系
        self._subject_to_request[subject] = (conversation_id, request_id)

        # 使用线程池执行邮件检查任务，而不是使用asyncio.create_task
        self._mail_check_tasks[(conversation_id, request_id)] = self._executor.submit(
            self._run_email_check_task,
            conversation_id,
            request_id,
            recipient_email,
            subject,
            timeout,
        )

        return HumanLoopResult(
            conversation_id=conversation_id,
            request_id=request_id,
            loop_type=HumanLoopType.CONVERSATION,
            status=HumanLoopStatus.PENDING,
        )

    async def async_cancel_request(self, conversation_id: str, request_id: str) -> bool:
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
        return await super().async_cancel_request(conversation_id, request_id)

    async def async_cancel_conversation(self, conversation_id: str) -> bool:
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
        return await super().async_cancel_conversation(conversation_id)

    def _extract_user_reply_content(self, body: str) -> str | None:
        """Extract the actual reply content from the email, excluding quoted original email content

        Args:
            body: Email body text

        Returns:
            str: User's actual reply content
        """
        # 首先尝试使用标记提取内容
        start_marker = self.templates["content_start_mark"]
        end_marker = self.templates["content_end_mark"]

        if start_marker in body and end_marker in body:
            start_index = body.find(start_marker) + len(start_marker)
            end_index = body.find(end_marker)
            if start_index < end_index:
                return body[start_index:end_index].strip()

        # 常见的邮件回复分隔符模式
        reply_patterns = [
            # 常见的邮件客户端引用标记
            r"On .* wrote:",  # Gmail, Apple Mail 等
            r"From: .*\n?Sent: .*\n?To: .*",  # Outlook
            r"-{3,}Original Message-{3,}",  # 一些邮件客户端
            r"From: [\w\s<>@.]+(\[mailto:[\w@.]+\])?\s+Sent:",  # Outlook 变体
            r"在.*写道：",  # 中文邮件客户端
            r"发件人: .*\n?时间: .*\n?收件人: .*",  # 中文 Outlook
            r">{3,}",  # 多级引用
            r"_{5,}",  # 分隔线
            r"\*{5,}",  # 分隔线
            r"={5,}",  # 分隔线
            r"原始邮件",  # 中文原始邮件
            r"请按以下格式回复：",  # 我们自己的指导语
            r"请直接回复您的内容。如需结束对话，请在回复中包含",  # 我们自己的指导语
        ]

        # 合并所有模式
        combined_pattern = "|".join(reply_patterns)

        # 尝试根据分隔符分割邮件内容
        parts = re.split(combined_pattern, body, flags=re.IGNORECASE)

        if parts and len(parts) > 1:
            # 第一部分通常是用户的回复
            user_content = parts[0].strip()

            # 如果没有找到明确的分隔符，尝试基于行分析
            lines = body.split("\n")
            user_content_lines = []

            for line in lines:
                # 跳过引用行（以 > 开头的行）
                if line.strip().startswith(">"):
                    continue
                # 如果遇到可能的分隔符，停止收集
                if any(
                    re.search(pattern, line, re.IGNORECASE)
                    for pattern in reply_patterns
                ):
                    break
                user_content_lines.append(line)

            user_content = "\n".join(user_content_lines).strip()

            # 清理用户内容中的多余换行符和空白
            # 1. 将所有 \r\n 替换为 \n
            user_content = user_content.replace("\r\n", "\n")

            # 2. 将连续的多个换行符替换为最多两个换行符
            user_content = re.sub(r"\n{3,}", "\n\n", user_content)

            # 3. 去除开头和结尾的空白行
            user_content = user_content.strip()

            # 4. 如果内容为空，返回一个友好的提示
            if not user_content or user_content.isspace():
                return "User didn't provide valid reply content"

            return user_content

        # 如果没有找到任何有效的用户回复内容，返回 None
        return None
