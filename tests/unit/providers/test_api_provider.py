import unittest

from pydantic import SecretStr

from gohumanloop.providers.api_provider import APIProvider


class TestAPIProviderInit(unittest.TestCase):
    """测试 APIProvider 类的初始化"""

    def test_init_with_required_params(self):
        """测试使用必需参数初始化"""
        provider = APIProvider(
            name="test_api_provider", api_base_url="https://api.example.com"
        )

        self.assertEqual(provider.name, "test_api_provider")
        self.assertEqual(provider.api_base_url, "https://api.example.com")
        self.assertIsNone(provider.api_key)
        self.assertIsNone(provider.default_platform)
        self.assertEqual(provider.request_timeout, 30)
        self.assertEqual(provider.poll_interval, 5)
        self.assertEqual(provider.max_retries, 3)
        self.assertEqual(provider.config, {})

    def test_init_with_all_params(self):
        """测试使用所有参数初始化"""
        api_key = SecretStr("test-api-key")
        config = {"prompt_template": "API: {context}", "other_config": "value"}

        provider = APIProvider(
            name="test_api_provider",
            api_base_url="https://api.example.com/",  # 测试末尾带斜杠的情况
            api_key=api_key,
            default_platform="wechat",
            request_timeout=60,
            poll_interval=10,
            max_retries=5,
            config=config,
        )

        self.assertEqual(provider.name, "test_api_provider")
        self.assertEqual(
            provider.api_base_url, "https://api.example.com"
        )  # 应该去掉末尾斜杠
        self.assertEqual(provider.api_key, api_key)
        self.assertEqual(provider.default_platform, "wechat")
        self.assertEqual(provider.request_timeout, 60)
        self.assertEqual(provider.poll_interval, 10)
        self.assertEqual(provider.max_retries, 5)
        self.assertEqual(provider.config, config)

    def test_str_representation(self):
        """测试字符串表示"""
        provider = APIProvider(
            name="test_api_provider",
            api_base_url="https://api.example.com",
            default_platform="wechat",
        )

        str_repr = str(provider)
        self.assertIn("API Provider", str_repr)
        self.assertIn("https://api.example.com", str_repr)
        self.assertIn("Default Platform: wechat", str_repr)
        self.assertIn("conversations=0", str_repr)
        self.assertIn("total_requests=0", str_repr)
        self.assertIn("active_requests=0", str_repr)
