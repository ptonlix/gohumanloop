import aiohttp
from typing import Dict, Any, Optional
import json
import asyncio
from datetime import datetime

from gohumanloop.providers.base import BaseProvider
from gohumanloop.core.interface import (
    HumanLoopResult, HumanLoopStatus, HumanLoopType
)

class APIProvider(BaseProvider):
    """通过API实现人机循环的提供者"""
    
    def __init__(self, api_url: str, api_key: Optional[str] = None, **kwargs):
        super().__init__(kwargs.get("config"))
        self.api_url = api_url
        self.api_key = api_key
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}" if api_key else ""
        }
        
    async def request_humanloop(
        self,
        task_id: str,
        loop_type: HumanLoopType,
        context: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
        conversation_id: Optional[str] = None
    ) -> HumanLoopResult:
        """通过API请求人机循环"""
        request_id = self._generate_request_id()
        metadata = metadata or {}
        
        # 存储请求信息
        self._store_request(
            request_id, 
            task_id, 
            loop_type,
            context, 
            metadata, 
            timeout,
            conversation_id
        )
        
        # 构建API请求
        payload = {
            "request_id": request_id,
            "task_id": task_id,
            "loop_type": loop_type.value,
            "context": context,
            "metadata": metadata,
            "timeout": timeout,
            "conversation_id": conversation_id
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_url}/human-loops", 
                    headers=self.headers,
                    json=payload
                ) as response:
                    if response.status == 200 or response.status == 201:
                        data = await response.json()
                        return HumanLoopResult(
                            request_id=request_id,
                            loop_type=loop_type,
                            status=HumanLoopStatus.PENDING,
                            feedback=data.get("feedback", {}),
                            conversation_id=conversation_id
                        )
                    else:
                        error_text = await response.text()
                        return HumanLoopResult(
                            request_id=request_id,
                            loop_type=loop_type,
                            status=HumanLoopStatus.ERROR,
                            error=f"API错误: {response.status} - {error_text}",
                            conversation_id=conversation_id
                        )
        except Exception as e:
            return HumanLoopResult(
                request_id=request_id,
                loop_type=loop_type,
                status=HumanLoopStatus.ERROR,
                error=f"请求错误: {str(e)}",
                conversation_id=conversation_id
            )
            
    async def check_humanloop_status(self, request_id: str) -> HumanLoopResult:
        """检查循环状态"""
        if request_id not in self._requests:
            return HumanLoopResult(
                request_id=request_id,
                loop_type=HumanLoopType.APPROVAL,  # 默认类型
                status=HumanLoopStatus.ERROR,
                error="请求ID不存在"
            )
            
        request_info = self._requests[request_id]
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.api_url}/human-loops/{request_id}", 
                    headers=self.headers
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        status_str = data.get("status", "pending")
                        
                        try:
                            status = HumanLoopStatus(status_str)
                        except ValueError:
                            status = HumanLoopStatus.ERROR
                            
                        return HumanLoopResult(
                            request_id=request_id,
                            loop_type=request_info["loop_type"],
                            status=status,
                            response=data.get("response", {}),
                            feedback=data.get("feedback", {}),
                            responded_by=data.get("responded_by"),
                            responded_at=data.get("responded_at"),
                            error=data.get("error"),
                            conversation_id=request_info.get("conversation_id")
                        )
                    else:
                        error_text = await response.text()
                        return HumanLoopResult(
                            request_id=request_id,
                            loop_type=request_info["loop_type"],
                            status=HumanLoopStatus.ERROR,
                            error=f"API错误: {response.status} - {error_text}",
                            conversation_id=request_info.get("conversation_id")
                        )
        except Exception as e:
            return HumanLoopResult(
                request_id=request_id,
                loop_type=request_info["loop_type"],
                status=HumanLoopStatus.ERROR,
                error=f"请求错误: {str(e)}",
                conversation_id=request_info.get("conversation_id")
            )
            
    async def continue_humanloop(
        self,
        request_id: str,
        context: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
        conversation_id: Optional[str] = None
    ) -> HumanLoopResult:
        """继续人机循环"""
        if request_id not in self._requests:
            return HumanLoopResult(
                request_id=request_id,
                loop_type=HumanLoopType.CONVERSATION,  # 默认为对话类型
                status=HumanLoopStatus.ERROR,
                error="请求ID不存在",
                conversation_id=conversation_id
            )
            
        request_info = self._requests[request_id]
        metadata = metadata or {}
        
        # 如果未提供conversation_id，使用请求信息中的值
        if not conversation_id and "conversation_id" in request_info:
            conversation_id = request_info["conversation_id"]
        
        # 更新请求信息
        request_info["context"] = context
        request_info["metadata"].update(metadata)
        if timeout:
            request_info["timeout"] = timeout
        if conversation_id:
            request_info["conversation_id"] = conversation_id
        request_info["status"] = HumanLoopStatus.INPROGRESS
        self._requests[request_id] = request_info
        
        # 构建API请求
        payload = {
            "context": context,
            "metadata": metadata,
            "timeout": timeout,
            "conversation_id": conversation_id
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_url}/human-loops/{request_id}/continue", 
                    headers=self.headers,
                    json=payload
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return HumanLoopResult(
                            request_id=request_id,
                            loop_type=request_info["loop_type"],
                            status=HumanLoopStatus.INPROGRESS,
                            feedback=data.get("feedback", {}),
                            conversation_id=conversation_id
                        )
                    else:
                        error_text = await response.text()
                        return HumanLoopResult(
                            request_id=request_id,
                            loop_type=request_info["loop_type"],
                            status=HumanLoopStatus.ERROR,
                            error=f"API错误: {response.status} - {error_text}",
                            conversation_id=conversation_id
                        )
        except Exception as e:
            return HumanLoopResult(
                request_id=request_id,
                loop_type=request_info["loop_type"],
                status=HumanLoopStatus.ERROR,
                error=f"请求错误: {str(e)}",
                conversation_id=conversation_id
            )
            
    async def cancel_humanloop(self, request_id: str) -> bool:
        """取消人机循环请求"""
        if request_id not in self._requests:
            return False
            
        try:
            async with aiohttp.ClientSession() as session:
                async with session.delete(
                    f"{self.api_url}/human-loops/{request_id}", 
                    headers=self.headers
                ) as response:
                    if response.status == 200 or response.status == 204:
                        # 从本地存储中删除请求
                        if request_id in self._requests:
                            del self._requests[request_id]
                        return True
                    else:
                        return False
        except Exception:
            # 即使API调用失败，也尝试从本地存储中删除
            if request_id in self._requests:
                del self._requests[request_id]
            return False