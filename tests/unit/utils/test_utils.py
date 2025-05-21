import os
import asyncio
import threading
import unittest
import pytest
from unittest.mock import patch
from unittest import IsolatedAsyncioTestCase
from pydantic import SecretStr

from gohumanloop.utils.utils import run_async_safely, get_secret_from_env
from gohumanloop.utils.threadsafedict import ThreadSafeDict


class TestRunAsyncSafely(unittest.TestCase):
    """测试异步安全运行功能"""

    def test_run_async_safely_with_existing_loop(self):
        """测试在已有事件循环的情况下运行异步函数"""

        async def sample_coro():
            return 42

        # 确保有一个事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = run_async_safely(sample_coro())
            self.assertEqual(result, 42)
        finally:
            loop.close()

    def test_run_async_safely_without_loop(self):
        """测试在没有事件循环的情况下运行异步函数"""

        async def sample_coro():
            return 42

        # 模拟没有事件循环的情况
        with patch("asyncio.get_event_loop", side_effect=RuntimeError):
            result = run_async_safely(sample_coro())
            self.assertEqual(result, 42)


class TestGetSecretFromEnv(unittest.TestCase):
    """测试环境变量获取和密钥处理功能"""

    def setUp(self):
        """设置测试环境变量"""
        os.environ["TEST_SECRET"] = "test_value"
        os.environ["TEST_SECRET_2"] = "test_value_2"

    def tearDown(self):
        """清理测试环境变量"""
        if "TEST_SECRET" in os.environ:
            del os.environ["TEST_SECRET"]
        if "TEST_SECRET_2" in os.environ:
            del os.environ["TEST_SECRET_2"]

    def test_get_secret_from_env_string_key(self):
        """测试使用字符串键获取环境变量"""
        secret = get_secret_from_env("TEST_SECRET")
        self.assertIsInstance(secret, SecretStr)
        self.assertEqual(secret.get_secret_value(), "test_value")

    def test_get_secret_from_env_list_key(self):
        """测试使用键列表获取环境变量"""
        secret = get_secret_from_env(["NONEXISTENT", "TEST_SECRET"])
        self.assertIsInstance(secret, SecretStr)
        self.assertEqual(secret.get_secret_value(), "test_value")

    def test_get_secret_from_env_tuple_key(self):
        """测试使用键元组获取环境变量"""
        secret = get_secret_from_env(("NONEXISTENT", "TEST_SECRET_2"))
        self.assertIsInstance(secret, SecretStr)
        self.assertEqual(secret.get_secret_value(), "test_value_2")

    def test_get_secret_from_env_with_default(self):
        """测试使用默认值获取环境变量"""
        secret = get_secret_from_env("NONEXISTENT", default="default_value")
        self.assertIsInstance(secret, SecretStr)
        self.assertEqual(secret.get_secret_value(), "default_value")

    def test_get_secret_from_env_none_default(self):
        """测试默认值为None的情况"""
        secret = get_secret_from_env("NONEXISTENT", default=None)
        self.assertIsNone(secret)


class TestThreadSafeDict(IsolatedAsyncioTestCase):
    """测试线程安全字典功能"""

    def test_sync_basic_operations(self):
        """测试同步基本操作"""
        d = ThreadSafeDict()

        # 测试设置和获取
        d["key1"] = "value1"
        self.assertEqual(d["key1"], "value1")

        # 测试键存在性检查
        self.assertTrue("key1" in d)
        self.assertFalse("key2" in d)

        # 测试获取默认值
        self.assertEqual(d.get("key1"), "value1")
        self.assertEqual(d.get("key2", "default"), "default")

        # 测试删除
        del d["key1"]
        self.assertFalse("key1" in d)

    def test_sync_dict_methods(self):
        """测试同步字典方法"""
        d = ThreadSafeDict()
        d["key1"] = "value1"
        d["key2"] = "value2"

        # 测试长度
        self.assertEqual(len(d), 2)

        # 测试键、值和键值对
        self.assertEqual(sorted(d.keys()), ["key1", "key2"])
        self.assertEqual(sorted(d.values()), ["value1", "value2"])
        self.assertEqual(sorted(d.items()), [("key1", "value1"), ("key2", "value2")])

    def test_sync_nested_dict_update(self):
        """测试同步嵌套字典更新"""
        d = ThreadSafeDict()
        d["nested"] = {"a": 1}

        # 测试更新整个字典
        self.assertTrue(d.update("nested", {"b": 2}))
        self.assertEqual(d["nested"], {"a": 1, "b": 2})

        # 测试更新单个项
        self.assertTrue(d.update_item("nested", "c", 3))
        self.assertEqual(d["nested"], {"a": 1, "b": 2, "c": 3})

        # 测试更新不存在的键
        self.assertFalse(d.update("nonexistent", {"x": 1}))
        self.assertFalse(d.update_item("nonexistent", "x", 1))

    @pytest.mark.asyncio(loop_scope="module")
    async def test_async_basic_operations(self):
        """测试异步基本操作"""
        d = ThreadSafeDict()

        # 测试设置和获取
        await d.aset("key1", "value1")
        self.assertEqual(await d.aget("key1"), "value1")

        # 测试键存在性检查
        self.assertTrue(await d.acontains("key1"))
        self.assertFalse(await d.acontains("key2"))

        # 测试获取默认值
        self.assertEqual(await d.aget("key1"), "value1")
        self.assertEqual(await d.aget("key2", "default"), "default")

        # 测试删除
        self.assertTrue(await d.adelete("key1"))
        self.assertFalse(await d.acontains("key1"))

        # 测试删除不存在的键
        self.assertFalse(await d.adelete("nonexistent"))

    @pytest.mark.asyncio(loop_scope="module")
    async def test_async_dict_methods(self):
        """测试异步字典方法"""
        d = ThreadSafeDict()
        await d.aset("key1", "value1")
        await d.aset("key2", "value2")

        # 测试长度
        self.assertEqual(await d.alen(), 2)

        # 测试键、值和键值对
        self.assertEqual(sorted(await d.akeys()), ["key1", "key2"])
        self.assertEqual(sorted(await d.avalues()), ["value1", "value2"])
        self.assertEqual(
            sorted(await d.aitems()), [("key1", "value1"), ("key2", "value2")]
        )

    @pytest.mark.asyncio(loop_scope="module")
    async def test_async_nested_dict_update(self):
        """测试异步嵌套字典更新"""
        d = ThreadSafeDict()
        await d.aset("nested", {"a": 1})

        # 测试更新整个字典
        self.assertTrue(await d.aupdate("nested", {"b": 2}))
        self.assertEqual(await d.aget("nested"), {"a": 1, "b": 2})

        # 测试更新单个项
        self.assertTrue(await d.aupdate_item("nested", "c", 3))
        self.assertEqual(await d.aget("nested"), {"a": 1, "b": 2, "c": 3})

        # 测试更新不存在的键
        self.assertFalse(await d.aupdate("nonexistent", {"x": 1}))
        self.assertFalse(await d.aupdate_item("nonexistent", "x", 1))

    def test_thread_safety(self):
        """测试多线程安全性"""
        d = ThreadSafeDict()
        num_threads = 10
        iterations = 100

        def worker():
            for i in range(iterations):
                key = f"key{threading.get_ident()}-{i}"
                d[key] = i
                # 读取操作
                _ = d.get(key)
                # 删除操作
                del d[key]

        threads = []
        for _ in range(num_threads):
            t = threading.Thread(target=worker)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # 验证字典为空
        self.assertEqual(len(d), 0)

    @pytest.mark.asyncio(loop_scope="module")
    async def test_async_concurrency(self):
        """测试异步并发安全性"""
        d = ThreadSafeDict()
        num_tasks = 10
        iterations = 100

        async def worker():
            for i in range(iterations):
                key = f"key{id(asyncio.current_task())}-{i}"
                await d.aset(key, i)
                # 读取操作
                _ = await d.aget(key)
                # 删除操作
                await d.adelete(key)

        tasks = [asyncio.create_task(worker()) for _ in range(num_tasks)]
        await asyncio.gather(*tasks)

        # 验证字典为空
        self.assertEqual(await d.alen(), 0)


if __name__ == "__main__":
    unittest.main()
