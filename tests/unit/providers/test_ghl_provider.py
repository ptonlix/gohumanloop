import unittest
from unittest.mock import patch


from gohumanloop.providers.ghl_provider import GoHumanLoopProvider


class TestGoHumanLoopProviderInit(unittest.TestCase):
    """测试 GoHumanLoopProvider 类的初始化"""

    @patch.dict(
        "os.environ",
        {
            "GOHUMANLOOP_API_KEY": "test-api-key",
            "GOHUMANLOOP_API_BASE_URL": "https://test.gohumanloop.com",
        },
    )
    def test_init_with_env_vars(self):
        """测试使用环境变量初始化"""
        provider = GoHumanLoopProvider(name="test_provider")

        self.assertEqual(provider.name, "test_provider")
        self.assertEqual(provider.api_base_url, "https://test.gohumanloop.com")
        self.assertEqual(provider.api_key.get_secret_value(), "test-api-key")
        self.assertEqual(provider.default_platform, "GoHumanLoop")
        self.assertEqual(provider.request_timeout, 30)
        self.assertEqual(provider.poll_interval, 5)
        self.assertEqual(provider.max_retries, 3)
        self.assertEqual(provider.config, {})

    @patch(
        "os.environ",
        {
            "GOHUMANLOOP_API_KEY": "test-api-key",
            "GOHUMANLOOP_API_BASE_URL": "https://www.gohumanloop.com",
        },
    )
    def test_init_with_default_api_url(self):
        """测试使用默认 API URL 初始化"""
        provider = GoHumanLoopProvider(name="test_provider")

        self.assertEqual(provider.api_base_url, "https://www.gohumanloop.com")
        self.assertEqual(provider.api_key.get_secret_value(), "test-api-key")

    def test_init_with_custom_params(self):
        """测试使用自定义参数初始化"""
        with patch("os.environ", {"GOHUMANLOOP_API_KEY": "test-api-key"}):
            provider = GoHumanLoopProvider(
                name="test_provider",
                request_timeout=60,
                poll_interval=10,
                max_retries=5,
                default_platform="custom_platform",
                config={"custom_key": "custom_value"},
            )

            self.assertEqual(provider.name, "test_provider")
            self.assertEqual(provider.request_timeout, 60)
            self.assertEqual(provider.poll_interval, 10)
            self.assertEqual(provider.max_retries, 5)
            self.assertEqual(provider.default_platform, "custom_platform")
            self.assertEqual(provider.config, {"custom_key": "custom_value"})

    def test_str_representation(self):
        """测试字符串表示"""
        with patch("os.environ", {"GOHUMANLOOP_API_KEY": "test-api-key"}):
            provider = GoHumanLoopProvider(name="test_provider")

            str_repr = str(provider)
            self.assertIn("GoHumanLoop Provider", str_repr)
            self.assertIn("Connected to GoHumanLoop Official Platform", str_repr)
            self.assertIn("https://www.gohumanloop.com", str_repr)
            self.assertIn("Default Platform: GoHumanLoop", str_repr)


class TestGoHumanLoopEnvironmentConfig(unittest.TestCase):
    """测试 GoHumanLoopProvider 环境变量配置功能"""

    @patch("os.environ", {})
    def test_missing_api_key(self):
        """测试缺少 API 密钥时的异常"""
        with self.assertRaises(ValueError) as context:
            GoHumanLoopProvider(name="test_provider")

        self.assertIn("validation error", str(context.exception))

    @patch(
        "os.environ",
        {
            "GOHUMANLOOP_API_KEY": "test-api-key",
            "GOHUMANLOOP_API_BASE_URL": "https://test.gohumanloop.com",
        },
    )
    def test_env_vars_priority(self):
        """测试环境变量优先级"""

        # 初始化提供者，但不传递 API 基础 URL
        provider = GoHumanLoopProvider(name="test_provider")

        # 验证环境变量中的值被使用
        self.assertEqual(provider.api_key.get_secret_value(), "test-api-key")
        self.assertEqual(provider.api_base_url, "https://test.gohumanloop.com")

    @patch("os.environ", {"GOHUMANLOOP_API_KEY": "env-api-key"})
    def test_custom_config_override(self):
        """测试自定义配置覆盖环境变量"""
        config = {"custom_setting": "value", "template": "Custom template: {message}"}

        provider = GoHumanLoopProvider(name="test_provider", config=config)

        self.assertEqual(provider.config, config)
        self.assertEqual(provider.api_key.get_secret_value(), "env-api-key")
