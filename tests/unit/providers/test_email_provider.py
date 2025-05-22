from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import MagicMock, patch

from pydantic import SecretStr

from gohumanloop.providers.email_provider import EmailProvider


class TestEmailProviderInit(TestCase):
    """测试 EmailProvider 类的初始化"""

    @patch(
        "os.environ",
        {
            "GOHUMANLOOP_EMAIL_USERNAME": "test@example.com",
            "GOHUMANLOOP_EMAIL_PASSWORD": "password123",
        },
    )
    def test_init_with_env_vars(self):
        """测试使用环境变量初始化"""
        provider = EmailProvider(
            name="test_provider",
            smtp_server="smtp.example.com",
            smtp_port=587,
            imap_server="imap.example.com",
            imap_port=993,
        )

        self.assertEqual(provider.name, "test_provider")
        self.assertEqual(provider.smtp_server, "smtp.example.com")
        self.assertEqual(provider.smtp_port, 587)
        self.assertEqual(provider.imap_server, "imap.example.com")
        self.assertEqual(provider.imap_port, 993)
        self.assertEqual(provider.username, "test@example.com")
        self.assertEqual(provider.sender_email, "test@example.com")
        self.assertEqual(provider.check_interval, 60)  # 默认值
        self.assertEqual(provider.language, "zh")  # 默认值

    def test_init_with_params(self):
        """测试使用参数初始化"""
        provider = EmailProvider(
            name="test_provider",
            smtp_server="smtp.example.com",
            smtp_port=587,
            imap_server="imap.example.com",
            imap_port=993,
            username="user@example.com",
            password=SecretStr("secure_password"),
            sender_email="sender@example.com",
            check_interval=30,
            language="en",
        )

        self.assertEqual(provider.name, "test_provider")
        self.assertEqual(provider.smtp_server, "smtp.example.com")
        self.assertEqual(provider.smtp_port, 587)
        self.assertEqual(provider.imap_server, "imap.example.com")
        self.assertEqual(provider.imap_port, 993)
        self.assertEqual(provider.username, "user@example.com")
        self.assertEqual(provider.sender_email, "sender@example.com")
        self.assertEqual(provider.check_interval, 30)
        self.assertEqual(provider.language, "en")

    def test_init_with_config(self):
        """测试使用配置初始化"""
        config = {"prompt_template": "Custom: {context}", "other_config": "value"}

        provider = EmailProvider(
            name="test_provider",
            smtp_server="smtp.example.com",
            smtp_port=587,
            imap_server="imap.example.com",
            imap_port=993,
            username="user@example.com",
            password=SecretStr("secure_password"),
            config=config,
        )

        self.assertEqual(provider.config, config)
        self.assertEqual(provider.prompt_template, "Custom: {context}")

    def test_init_language_templates(self):
        """测试不同语言模板初始化"""
        # 测试中文模板
        provider_zh = EmailProvider(
            name="test_provider_zh",
            smtp_server="smtp.example.com",
            smtp_port=587,
            imap_server="imap.example.com",
            imap_port=993,
            username="user@example.com",
            password=SecretStr("secure_password"),
            language="zh",
        )

        self.assertEqual(provider_zh.language, "zh")
        self.assertIn("批准", provider_zh.approve_keywords)
        self.assertIn("拒绝", provider_zh.reject_keywords)
        self.assertEqual(provider_zh.templates["decision_prefix"], "决定：")

        # 测试英文模板
        provider_en = EmailProvider(
            name="test_provider_en",
            smtp_server="smtp.example.com",
            smtp_port=587,
            imap_server="imap.example.com",
            imap_port=993,
            username="user@example.com",
            password=SecretStr("secure_password"),
            language="en",
        )

        self.assertEqual(provider_en.language, "en")
        self.assertIn("approve", provider_en.approve_keywords)
        self.assertIn("reject", provider_en.reject_keywords)
        self.assertEqual(provider_en.templates["decision_prefix"], "Decision: ")

    @patch("os.environ", {})
    def test_init_missing_username(self):
        """测试缺少用户名时的异常"""
        with self.assertRaises(ValueError) as context:
            EmailProvider(
                name="test_provider",
                smtp_server="smtp.example.com",
                smtp_port=587,
                imap_server="imap.example.com",
                imap_port=993,
            )

        self.assertIn("Email username not provided", str(context.exception))

    @patch("os.environ", {"GOHUMANLOOP_EMAIL_USERNAME": "test@example.com"})
    def test_init_missing_password(self):
        """测试缺少密码时的异常"""
        with self.assertRaises(ValueError) as context:
            EmailProvider(
                name="test_provider",
                smtp_server="smtp.example.com",
                smtp_port=587,
                imap_server="imap.example.com",
                imap_port=993,
                username="user@example.com",
            )

        self.assertIn("Email password not provided", str(context.exception))


class TestEmailSending(IsolatedAsyncioTestCase):
    """测试邮件发送功能"""

    def setUp(self):
        """设置测试环境"""
        self.provider = EmailProvider(
            name="test_provider",
            smtp_server="smtp.example.com",
            smtp_port=587,
            imap_server="imap.example.com",
            imap_port=993,
            username="user@example.com",
            password=SecretStr("secure_password"),
        )

    @patch("gohumanloop.providers.email_provider.smtplib.SMTP_SSL")
    async def test_send_email_success(self, mock_smtp):
        """测试成功发送邮件"""
        # 设置模拟对象
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        # 调用发送邮件方法
        result = await self.provider._send_email(
            to_email="recipient@example.com", subject="Test Subject", body="Test Body"
        )

        # 验证结果
        self.assertTrue(result)
        mock_smtp.assert_called_once_with("smtp.example.com", 587)
        mock_server.login.assert_called_once_with("user@example.com", "secure_password")
        mock_server.send_message.assert_called_once()

    @patch("gohumanloop.providers.email_provider.smtplib.SMTP_SSL")
    async def test_send_email_with_html(self, mock_smtp):
        """测试发送HTML格式邮件"""
        # 设置模拟对象
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        # 调用发送邮件方法
        result = await self.provider._send_email(
            to_email="recipient@example.com",
            subject="Test Subject",
            body="Test Body",
            html_body="<html><body><p>Test HTML Body</p></body></html>",
        )

        # 验证结果
        self.assertTrue(result)
        mock_smtp.assert_called_once_with("smtp.example.com", 587)
        mock_server.login.assert_called_once_with("user@example.com", "secure_password")
        mock_server.send_message.assert_called_once()

    @patch("gohumanloop.providers.email_provider.smtplib.SMTP_SSL")
    async def test_send_email_with_reply_to(self, mock_smtp):
        """测试发送带回复ID的邮件"""
        # 设置模拟对象
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        # 调用发送邮件方法
        result = await self.provider._send_email(
            to_email="recipient@example.com",
            subject="Test Subject",
            body="Test Body",
            reply_to="<message-id@example.com>",
        )

        # 验证结果
        self.assertTrue(result)
        mock_smtp.assert_called_once_with("smtp.example.com", 587)
        mock_server.login.assert_called_once_with("user@example.com", "secure_password")
        mock_server.send_message.assert_called_once()

    @patch("gohumanloop.providers.email_provider.smtplib.SMTP_SSL")
    async def test_send_email_failure(self, mock_smtp):
        """测试发送邮件失败"""
        # 设置模拟对象抛出异常
        mock_smtp.return_value.__enter__.side_effect = Exception("Connection error")

        # 调用发送邮件方法
        result = await self.provider._send_email(
            to_email="recipient@example.com", subject="Test Subject", body="Test Body"
        )

        # 验证结果
        self.assertFalse(result)
