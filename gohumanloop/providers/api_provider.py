import aiohttp
from typing import Dict, Any, Optional
import json
import asyncio

from gohumanloop.providers.base import BaseProvider
from gohumanloop.core.interface import ApprovalResult, ApprovalStatus

class APIProvider(BaseProvider):
    """通过API实现人机交互的提供者"""
    
    def __init__(self, api_url: str, api_key: Optional[str] = None, **kwargs):
        super().__init__(kwargs.get("config"))
        self.api_url = api_url
        self.api_key = api_key
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}" if api_key else ""
        }
        
    async def request_approval(
        self,
        task_id: str,
        context: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None
    ) -> ApprovalResult:
        """通过API请求人类批准"""
        request_id = self._generate_request_id()
        metadata = metadata or {}
        
        # 存储请求信息
        self._store_request(request_id, task_id, context, metadata, timeout)
        
        # 构建API请求
        payload = {
            "request_id": request_id,
            "task_id": task_id,
            "context": context,
            "metadata": metadata,
            "timeout": timeout
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_url}/approvals", 
                    headers=self.headers,
                    json=payload
                ) as response:
                    if response.status == 200 or response.status == 201:
                        data = await response.json()
                        return ApprovalResult(
                            request_id=request_id,
                            status=ApprovalStatus.PENDING,
                            feedback=data.get("feedback")
                        )
                    else:
                        error_text = await response.text()
                        return ApprovalResult(
                            request_id=request_id,
                            status=ApprovalStatus.ERROR,
                            error=f"API错误: {response.status} - {error_text}"
                        )
        except Exception as e:
            return ApprovalResult(
                request_id=request_id,
                status=ApprovalStatus.ERROR,
                error=f"请求错误: {str(e)}"
            )
            
    async def check_approval_status(self, request_id: str) -> ApprovalResult:
        """通过API检查批准状态"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.api_url}/approvals/{request_id}", 
                    headers=self.headers
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        status_str = data.get("status", "pending").lower()
                        
                        # 将字符串状态转换为枚举
                        status_map = {
                            "pending": ApprovalStatus.PENDING,
                            "approved": ApprovalStatus.APPROVED,
                            "rejected": ApprovalStatus.REJECTED,
                            "expired": ApprovalStatus.EXPIRED,
                            "error": ApprovalStatus.ERROR
                        }
                        status = status_map.get(status_str, ApprovalStatus.PENDING)
                        
                        return ApprovalResult(
                            request_id=request_id,
                            status=status,
                            feedback=data.get("feedback"),
                            approved_by=data.get("approved_by"),
                            approved_at=data.get("approved_at")
                        )
                    else:
                        error_text = await response.text()
                        return ApprovalResult(
                            request_id=request_id,
                            status=ApprovalStatus.ERROR,
                            error=f"API错误: {response.status} - {error_text}"
                        )
        except Exception as e:
            return ApprovalResult(
                request_id=request_id,
                status=ApprovalStatus.ERROR,
                error=f"请求错误: {str(e)}"
            )
            
    async def cancel_approval_request(self, request_id: str) -> bool:
        """通过API取消批准请求"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.delete(
                    f"{self.api_url}/approvals/{request_id}", 
                    headers=self.headers
                ) as response:
                    if response.status == 200 or response.status == 204:
                        # 同时从本地存储中删除
                        return await super().cancel_approval_request(request_id)
                    return False
        except Exception:
            return False