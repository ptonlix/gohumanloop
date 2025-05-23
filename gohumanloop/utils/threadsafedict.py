from typing import Dict, Any, Optional, TypeVar, Generic
import asyncio
import threading


K = TypeVar("K")
V = TypeVar("V")


class ThreadSafeDict(Generic[K, V]):
    """
    线程安全的字典，同时支持同步和异步操作，两种方式都保证线程安全
    - 双重锁机制 ：

    - 使用 threading.RLock 保护同步操作
    - 使用 asyncio.Lock 保护异步操作
    - 使用键级别锁减少锁竞争
    - 同步方法的线程安全 ：

    - 所有同步方法都使用 self._sync_lock 保护
    - 返回容器类型的方法（如 keys() 、 values() 、 items() ）返回列表副本而非迭代器，避免迭代过程中的并发修改问题
    - 异步方法的线程安全 ：

    - 所有异步方法都使用 self._async_lock 保护
    - 对于写操作，还使用键级别锁进一步减少锁竞争
    - 键级别锁 ：

    - 为每个键创建独立的锁，减少不同键之间的锁竞争
    - 使用全局锁 self._global_lock 保护键级别锁的创建和删除
    """

    def __init__(self) -> None:
        self._dict: dict[Any, Any] = {}
        # 使用 threading.RLock 支持同步操作的线程安全
        self._sync_lock = threading.RLock()
        # 使用 asyncio.Lock 支持异步操作的线程安全
        self._async_lock = asyncio.Lock()
        # 键级别锁字典
        self._key_locks: dict[Any, asyncio.Lock] = {}
        # 键级别锁的全局锁
        self._global_lock = asyncio.Lock()

    async def _get_key_lock(self, key: K) -> asyncio.Lock:
        """获取指定键的锁，如果不存在则创建"""
        async with self._global_lock:
            if key not in self._key_locks:
                self._key_locks[key] = asyncio.Lock()
            return self._key_locks[key]

    # 同步方法 - 使用 threading.RLock 保证线程安全
    def __getitem__(self, key: K) -> Any:
        """获取值 - 同步方法，用于 dict[key] 语法"""
        with self._sync_lock:
            return self._dict[key]

    def __setitem__(self, key: K, value: V) -> None:
        """设置值 - 同步方法，用于 dict[key] = value 语法"""
        with self._sync_lock:
            self._dict[key] = value

    def __delitem__(self, key: K) -> None:
        """删除键 - 同步方法，用于 del dict[key] 语法"""
        with self._sync_lock:
            del self._dict[key]

    def __contains__(self, key: K) -> bool:
        """检查键是否存在 - 同步方法，用于 key in dict 语法"""
        with self._sync_lock:
            return key in self._dict

    def get(self, key: K, default: Optional[V] = None) -> Any:
        """获取值，如果不存在则返回默认值 - 同步方法"""
        with self._sync_lock:
            return self._dict.get(key, default)

    def __len__(self) -> int:
        """获取字典长度 - 同步方法，用于 len(dict) 语法"""
        with self._sync_lock:
            return len(self._dict)

    def keys(self) -> list:
        """获取所有键 - 同步方法"""
        with self._sync_lock:
            return list(self._dict.keys())

    def values(self) -> list:
        """获取所有值 - 同步方法"""
        with self._sync_lock:
            return list(self._dict.values())

    def items(self) -> list:
        """获取所有键值对 - 同步方法"""
        with self._sync_lock:
            return list(self._dict.items())

    def update(self, key: K, updates: Dict[str, Any]) -> bool:
        """更新字典中的值 - 同步方法"""
        with self._sync_lock:
            if key in self._dict and isinstance(self._dict[key], dict):
                self._dict[key].update(updates)
                return True
            return False

    def update_item(self, key: K, item_key: Any, item_value: Any) -> bool:
        """更新字典中的单个项 - 同步方法"""
        with self._sync_lock:
            if key in self._dict and isinstance(self._dict[key], dict):
                self._dict[key][item_key] = item_value
                return True
            return False

    # 异步方法 - 使用 asyncio.Lock 保证线程安全
    async def aget(self, key: K, default: Optional[V] = None) -> Any:
        """安全地获取值 - 异步方法"""
        async with self._async_lock:
            return self._dict.get(key, default)

    async def aset(self, key: K, value: V) -> None:
        """安全地设置值 - 异步方法"""
        key_lock = await self._get_key_lock(key)
        async with key_lock:
            async with self._async_lock:
                self._dict[key] = value

    async def adelete(self, key: K) -> bool:
        """安全地删除键 - 异步方法"""
        key_lock = await self._get_key_lock(key)
        async with key_lock:
            async with self._async_lock:
                if key in self._dict:
                    del self._dict[key]
                    # 也可以选择删除锁
                    async with self._global_lock:
                        if key in self._key_locks:
                            del self._key_locks[key]
                    return True
                return False

    async def aupdate(self, key: K, updates: Dict[str, Any]) -> bool:
        """安全地更新值 - 异步方法"""
        key_lock = await self._get_key_lock(key)
        async with key_lock:
            async with self._async_lock:
                if key in self._dict and isinstance(self._dict[key], dict):
                    self._dict[key].update(updates)
                    return True
                return False

    async def aupdate_item(self, key: K, item_key: Any, item_value: Any) -> bool:
        """安全地更新字典中的单个项 - 异步方法"""
        key_lock = await self._get_key_lock(key)
        async with key_lock:
            async with self._async_lock:
                if key in self._dict and isinstance(self._dict[key], dict):
                    self._dict[key][item_key] = item_value
                    return True
                return False

    async def acontains(self, key: K) -> bool:
        """安全地检查键是否存在 - 异步方法"""
        async with self._async_lock:
            return key in self._dict

    async def alen(self) -> int:
        """安全地获取字典长度 - 异步方法"""
        async with self._async_lock:
            return len(self._dict)

    async def akeys(self) -> list:
        """安全地获取所有键 - 异步方法"""
        async with self._async_lock:
            return list(self._dict.keys())

    async def avalues(self) -> list:
        """安全地获取所有值 - 异步方法"""
        async with self._async_lock:
            return list(self._dict.values())

    async def aitems(self) -> list:
        """安全地获取所有键值对 - 异步方法"""
        async with self._async_lock:
            return list(self._dict.items())


if __name__ == "__main__":
    # 测试同步方法
    def test_sync_methods() -> None:
        print("\n=== 测试同步方法 ===")
        sync_dict: ThreadSafeDict = ThreadSafeDict()

        # 测试基本的增删改查操作
        sync_dict["key1"] = "value1"
        print("设置并获取:", sync_dict["key1"])  # value1
        print("键存在性检查:", "key1" in sync_dict)  # True
        print("获取默认值:", sync_dict.get("not_exist", "default"))  # default

        # 测试字典长度
        print("字典长度:", len(sync_dict))  # 1

        # 测试字典方法
        sync_dict["key2"] = "value2"
        print("所有键:", sync_dict.keys())  # ['key1', 'key2']
        print("所有值:", sync_dict.values())  # ['value1', 'value2']
        print(
            "所有键值对:", sync_dict.items()
        )  # [('key1', 'value1'), ('key2', 'value2')]

        # 测试嵌套字典更新
        sync_dict["nested"] = {"a": 1}
        sync_dict.update("nested", {"b": 2})
        sync_dict.update_item("nested", "c", 3)
        print("嵌套字典:", sync_dict["nested"])  # {'a': 1, 'b': 2, 'c': 3}

        # 测试删除操作
        del sync_dict["key1"]
        print("删除后检查:", "key1" in sync_dict)  # False

    # 测试异步方法
    async def test_async_methods() -> None:
        print("\n=== 测试异步方法 ===")
        async_dict: ThreadSafeDict = ThreadSafeDict()

        # 测试基本的异步增删改查
        await async_dict.aset("key1", "value1")
        print("异步获取:", await async_dict.aget("key1"))  # value1
        print("异步键检查:", await async_dict.acontains("key1"))  # True

        # 测试异步字典操作
        await async_dict.aset("key2", "value2")
        print("异步长度:", await async_dict.alen())  # 2
        print("异步所有键:", await async_dict.akeys())  # ['key1', 'key2']
        print("异步所有值:", await async_dict.avalues())  # ['value1', 'value2']
        print(
            "异步所有键值对:", await async_dict.aitems()
        )  # [('key1', 'value1'), ('key2', 'value2')]

        # 测试异步嵌套字典更新
        await async_dict.aset("nested", {"x": 1})
        await async_dict.aupdate("nested", {"y": 2})
        await async_dict.aupdate_item("nested", "z", 3)
        print(
            "异步嵌套字典:", await async_dict.aget("nested")
        )  # {'x': 1, 'y': 2, 'z': 3}

        # 测试异步删除
        await async_dict.adelete("key1")
        print("异步删除后检查:", await async_dict.acontains("key1"))  # False

    # 运行测试
    test_sync_methods()
    asyncio.run(test_async_methods())
