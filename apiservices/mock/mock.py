import asyncio
import json
import logging
import random
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any

from fastapi import FastAPI, HTTPException, Header, Depends, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 定义数据模型
class APIResponse(BaseModel):
    """API 响应基础模型"""
    success: bool = Field(default=False, description="请求是否成功")
    error: Optional[str] = Field(default=None, description="错误信息（如有）")

class HumanLoopRequestData(BaseModel):
    """人机循环请求数据模型"""
    task_id: str = Field(description="任务标识符")
    conversation_id: str = Field(description="对话标识符")
    request_id: str = Field(description="请求标识符")
    loop_type: str = Field(description="循环类型")
    context: Dict[str, Any] = Field(description="提供给人类的上下文信息")
    platform: str = Field(description="使用的平台，例如 wechat, feishu")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="附加元数据")

class HumanLoopStatusParams(BaseModel):
    """获取人机循环状态的参数模型"""
    conversation_id: str = Field(description="对话标识符")
    request_id: str = Field(description="请求标识符")
    platform: str = Field(description="使用的平台")

class HumanLoopStatusResponse(APIResponse):
    """人机循环状态响应模型"""
    status: str = Field(default="pending", description="请求状态")
    response: Optional[Any] = Field(default=None, description="人类响应数据")
    feedback: Optional[Any] = Field(default=None, description="反馈数据")
    responded_by: Optional[str] = Field(default=None, description="响应者信息")
    responded_at: Optional[str] = Field(default=None, description="响应时间戳")

class HumanLoopCancelData(BaseModel):
    """取消人机循环请求的数据模型"""
    conversation_id: str = Field(description="对话标识符")
    request_id: str = Field(description="请求标识符")
    platform: str = Field(description="使用的平台")

class HumanLoopCancelConversationData(BaseModel):
    """取消整个对话的数据模型"""
    conversation_id: str = Field(description="对话标识符")
    platform: str = Field(description="使用的平台")

class HumanLoopContinueData(BaseModel):
    """继续人机循环交互的数据模型"""
    conversation_id: str = Field(description="对话标识符")
    request_id: str = Field(description="请求标识符")
    task_id: str = Field(description="任务标识符")
    context: Dict[str, Any] = Field(description="提供给人类的上下文信息")
    platform: str = Field(description="使用的平台")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="附加元数据")

# 创建 FastAPI 应用
app = FastAPI(title="GoHumanLoop Mock Server", description="Mock API for GoHumanLoop service")

# API 密钥验证（简单实现）
API_KEYS = {"gohumanloop": "admin"}

def verify_api_key(x_api_key: Optional[str] = Header(None)):
    """验证 API 密钥"""
    if x_api_key not in API_KEYS:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key

# 创建需要验证的路由组
api_router = APIRouter(
    prefix="/humanloop",
    dependencies=[Depends(verify_api_key)]
)

# 添加 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 存储请求数据
requests_store: Dict[str, Dict[str, Any]] = {}
conversations_store: Dict[str, List[str]] = {}

# 模拟自动响应任务
auto_response_tasks = {}

# 模拟自动响应
async def auto_respond(conversation_id: str, request_id: str, delay: int = 5):
    """模拟自动响应"""
    await asyncio.sleep(delay)
    
    # 检查请求是否仍然存在（可能已被取消）
    request_key = f"{conversation_id}:{request_id}"
    if request_key not in requests_store:
        return
        
    request_data = requests_store[request_key]
    
    # 根据循环类型生成不同的响应
    loop_type = request_data.get("loop_type", "conversation")
    
    if loop_type == "approval":
        # 随机批准或拒绝
        decision = random.choice(["approved", "rejected"])
        response = {
            "decision": decision,
            "reason": f"这是一个自动{decision}的理由"
        }
        status = "approved" if decision == "approved" else "rejected"
    elif loop_type == "information":
        # 提供一些模拟信息
        response = {
            "information": "这是一些模拟的信息内容"
        }
        status = "completed"
    else:  #conversation
        # 检查是否是该对话的第二次请求
        conversation_requests = conversations_store.get(conversation_id, [])
        is_second_request = len(conversation_requests) > 1 and request_id == conversation_requests[-1]
        
        # 模拟对话响应
        response = {
            "message": "这是一个自动生成的对话响应"
        }
        status = "completed" if is_second_request else "inprogress"
        
    # 更新请求状态
    requests_store[request_key].update({
        "status": status,
        "response": response,
        "responded_by": "mock_user@example.com",
        "responded_at": datetime.now().isoformat()
    })


@api_router.post("/request", response_model=APIResponse)
async def request_humanloop(data: HumanLoopRequestData):
    """创建人机循环请求"""
    logger.info(f"收到请求: {data.model_dump_json()}")
    
    # 存储请求
    request_key = f"{data.conversation_id}:{data.request_id}"
    requests_store[request_key] = {
        "task_id": data.task_id,
        "conversation_id": data.conversation_id,
        "request_id": data.request_id,
        "loop_type": data.loop_type,
        "context": data.context,
        "platform": data.platform,
        "metadata": data.metadata,
        "status": "pending",
        "created_at": datetime.now().isoformat()
    }
    
    # 更新对话存储
    if data.conversation_id not in conversations_store:
        conversations_store[data.conversation_id] = []
    conversations_store[data.conversation_id].append(data.request_id)
    
    # 创建自动响应任务
    delay = random.randint(5, 15)  # 随机延迟5-15秒
    task = asyncio.create_task(auto_respond(data.conversation_id, data.request_id, delay))
    auto_response_tasks[request_key] = task
    
    return APIResponse(success=True)

@api_router.get("/status", response_model=HumanLoopStatusResponse)
async def check_status(conversation_id: str, request_id: str, platform: str):
    """检查人机循环请求状态"""
    request_key = f"{conversation_id}:{request_id}"
    
    if request_key not in requests_store:
        return HumanLoopStatusResponse(
            success=False,
            error=f"Request not found: {request_id}"
        )
    
    request_data = requests_store[request_key]
    
    return HumanLoopStatusResponse(
        success=True,
        status=request_data.get("status", "pending"),
        response=request_data.get("response"),
        feedback=request_data.get("feedback"),
        responded_by=request_data.get("responded_by"),
        responded_at=request_data.get("responded_at")
    )

@api_router.post("/cancel", response_model=APIResponse)
async def cancel_request(data: HumanLoopCancelData, api_key: str = Depends(verify_api_key)):
    """取消人机循环请求"""
    request_key = f"{data.conversation_id}:{data.request_id}"
    
    if request_key not in requests_store:
        return APIResponse(
            success=False,
            error=f"Request not found: {data.request_id}"
        )
    
    # 取消自动响应任务
    if request_key in auto_response_tasks:
        auto_response_tasks[request_key].cancel()
        del auto_response_tasks[request_key]
    
    # 更新请求状态
    requests_store[request_key]["status"] = "cancelled"
    
    return APIResponse(success=True)

@api_router.post("/cancel_conversation", response_model=APIResponse)
async def cancel_conversation(data: HumanLoopCancelConversationData, api_key: str = Depends(verify_api_key)):
    """取消整个对话"""
    if data.conversation_id not in conversations_store:
        return APIResponse(
            success=False,
            error=f"Conversation not found: {data.conversation_id}"
        )
    
    # 取消对话中的所有请求
    for request_id in conversations_store[data.conversation_id]:
        request_key = f"{data.conversation_id}:{request_id}"
        
        # 取消自动响应任务
        if request_key in auto_response_tasks:
            auto_response_tasks[request_key].cancel()
            del auto_response_tasks[request_key]
        
        # 更新请求状态
        if request_key in requests_store:
            requests_store[request_key]["status"] = "cancelled"
    
    return APIResponse(success=True)

@api_router.post("/continue", response_model=APIResponse)
async def continue_humanloop(data: HumanLoopContinueData, api_key: str = Depends(verify_api_key)):
    """继续人机循环交互"""
    # 检查对话是否存在
    if data.conversation_id not in conversations_store:
        return APIResponse(
            success=False,
            error=f"Conversation not found: {data.conversation_id}"
        )
    
    
    # 存储请求
    request_key = f"{data.conversation_id}:{data.request_id}"
    requests_store[request_key] = {
        "task_id": data.task_id,
        "conversation_id": data.conversation_id,
        "request_id": data.request_id,
        "loop_type": "conversation",  # 继续对话默认为对话类型
        "context": data.context,
        "platform": data.platform,
        "metadata": data.metadata,
        "status": "pending",
        "created_at": datetime.now().isoformat()
    }
    
    # 更新对话存储
    conversations_store[data.conversation_id].append(data.request_id)
    
    # 创建自动响应任务
    delay = random.randint(5, 15)  # 随机延迟5-15秒
    task = asyncio.create_task(auto_respond(data.conversation_id, data.request_id, delay))
    auto_response_tasks[request_key] = task
    
    return APIResponse(success=True)

# 健康检查不需要验证
@app.get("/health")
async def health_check():
    """健康检查接口"""
    return {"status": "ok"}

# 将路由组添加到应用
app.include_router(api_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)