import os
from typing import Dict, Any, Optional
import json
from pathlib import Path

class Settings:
    """配置设置管理器"""
    
    def __init__(self, config_file: Optional[str] = None):
        self._config = {}
        self._config_file = config_file
        
        # 加载默认配置
        self._load_defaults()
        
        # 加载环境变量
        self._load_from_env()
        
        # 加载配置文件（如果指定）
        if config_file:
            self._load_from_file(config_file)
            
    def _load_defaults(self):
        """加载默认配置"""
        self._config = {
            "api": {
                "url": "https://api.gohumanloop.com",
                "timeout": 30,
                "retry_attempts": 3,
                "retry_delay": 1.0
            },
            "approval": {
                "default_timeout": 300,  # 5分钟
                "polling_interval": 2.0
            },
            "logging": {
                "level": "INFO",
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            }
        }
        
    def _load_from_env(self):
        """从环境变量加载配置"""
        # API配置
        if "GOHUMANLOOP_API_URL" in os.environ:
            self._config["api"]["url"] = os.environ["GOHUMANLOOP_API_URL"]
            
        if "GOHUMANLOOP_API_KEY" in os.environ:
            self._config["api"]["key"] = os.environ["GOHUMANLOOP_API_KEY"]
            
        if "GOHUMANLOOP_API_TIMEOUT" in os.environ:
            self._config["api"]["timeout"] = int(os.environ["GOHUMANLOOP_API_TIMEOUT"])
            
        # 批准配置
        if "GOHUMANLOOP_APPROVAL_TIMEOUT" in os.environ:
            self._config["approval"]["default_timeout"] = int(os.environ["GOHUMANLOOP_APPROVAL_TIMEOUT"])
            
        if "GOHUMANLOOP_POLLING_INTERVAL" in os.environ:
            self._config["approval"]["polling_interval"] = float(os.environ["GOHUMANLOOP_POLLING_INTERVAL"])
            
        # 日志配置
        if "GOHUMANLOOP_LOG_LEVEL" in os.environ:
            self._config["logging"]["level"] = os.environ["GOHUMANLOOP_LOG_LEVEL"]
            
    def _load_from_file(self, config_file: str):
        """从文件加载配置"""
        path = Path(config_file)
        if not path.exists():
            return
            
        with open(path, "r") as f:
            file_config = json.load(f)
            
        # 递归更新配置
        self._update_config(self._config, file_config)
        
    def _update_config(self, target: Dict[str, Any], source: Dict[str, Any]):
        """递归更新配置"""
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                self._update_config(target[key], value)
            else:
                target[key] = value
                
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        keys = key.split(".")
        config = self._config
        
        for k in keys:
            if k not in config:
                return default
            config = config[k]
            
        return config
        
    def set(self, key: str, value: Any):
        """设置配置值"""
        keys = key.split(".")
        config = self._config
        
        for i, k in enumerate(keys[:-1]):
            if k not in config:
                config[k] = {}
            config = config[k]
            
        config[keys[-1]] = value
        
    def save(self, config_file: Optional[str] = None):
        """保存配置到文件"""
        # 处理配置文件路径，确保不为None
        if config_file is not None:
            path = Path(config_file)
        elif self._config_file is not None:
            path = Path(self._config_file)
        else:
            path = None
        if not path:
            raise ValueError("No config file specified")
            
        # 确保目录存在
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, "w") as f:
            json.dump(self._config, f, indent=2)