import asyncio
import json
import logging
import random
from datetime import datetime
from typing import Dict, List, Optional, Any

from fastapi import FastAPI, HTTPException, Header, Depends, APIRouter, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
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

# 新增：任务数据同步模型
class TaskSyncData(BaseModel):
    """任务数据同步模型"""
    task_id: str = Field(description="任务标识符")
    conversations: List[Dict[str, Any]] = Field(description="对话数据列表")
    timestamp: str = Field(description="时间戳")

# 创建 FastAPI 应用
app = FastAPI(title="GoHumanLoop Mock Server", description="Mock API for GoHumanLoop service")

# API 密钥验证（简单实现）
API_KEYS = {"gohumanloop": "admin"}

def verify_api_key(authorization: Optional[str] = Header(None)):
    """验证 API 密钥（Bearer Token 方式）"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")
        
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid authorization format. Use 'Bearer TOKEN'")
        
    token = parts[1]
    if token not in API_KEYS:
        raise HTTPException(status_code=401, detail="Invalid API token")
    return token

# 创建需要验证的路由组
api_router = APIRouter(
    prefix="/api/v1/humanloop",
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

# 新增：存储同步的任务数据
tasks_store: Dict[str, Dict[str, Any]] = {}

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
async def cancel_request(data: HumanLoopCancelData, token: str = Depends(verify_api_key)):
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
async def cancel_conversation(data: HumanLoopCancelConversationData, token: str = Depends(verify_api_key)):
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
async def continue_humanloop(data: HumanLoopContinueData, token: str = Depends(verify_api_key)):
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

# 新增：接收任务数据同步的路由
@api_router.post("/tasks/sync", response_model=APIResponse)
async def sync_task_data(data: Dict[str, Any], token: str = Depends(verify_api_key)):
    """接收任务数据同步"""
    logger.info(f"收到任务数据同步: {json.dumps(data)[:200]}...")  # 只记录前200个字符
    
    task_id = data.get("task_id")
    if not task_id:
        return APIResponse(
            success=False,
            error="Missing task_id"
        )
    
    # 检查任务是否已存在
    if task_id in tasks_store:
        # 获取现有数据
        existing_data = tasks_store[task_id].get("data", {})
        existing_conversations = existing_data.get("conversations", [])
        
        # 获取新数据中的对话
        new_conversations = data.get("conversations", [])
        
        # 创建对话ID到索引的映射，用于快速查找
        conv_map = {conv.get("conversation_id"): idx for idx, conv in enumerate(existing_conversations)}
        
        # 合并对话数据
        for new_conv in new_conversations:
            conv_id = new_conv.get("conversation_id")
            if conv_id in conv_map:
                # 对话已存在，更新或追加请求
                existing_conv = existing_conversations[conv_map[conv_id]]
                existing_requests = {req.get("request_id"): req for req in existing_conv.get("requests", [])}
                
                # 处理新请求
                for new_req in new_conv.get("requests", []):
                    req_id = new_req.get("request_id")
                    if req_id:
                        existing_requests[req_id] = new_req
                
                # 更新请求列表
                existing_conv["requests"] = list(existing_requests.values())
            else:
                # 对话不存在，直接添加
                existing_conversations.append(new_conv)
        
        # 更新数据
        updated_data = existing_data.copy()
        updated_data["conversations"] = existing_conversations
        updated_data["timestamp"] = data.get("timestamp", datetime.now().isoformat())
        
        # 存储更新后的数据
        tasks_store[task_id] = {
            "data": updated_data,
            "received_at": datetime.now().isoformat(),
            "updates": tasks_store[task_id].get("updates", 0) + 1
        }
    else:
        # 任务不存在，创建新任务
        tasks_store[task_id] = {
            "data": data,
            "received_at": datetime.now().isoformat(),
            "updates": 1
        }
    
    return APIResponse(success=True)

# 新增：获取所有任务数据的路由
@api_router.get("/tasks", response_model=Dict[str, Any])
async def get_all_tasks(token: str = Depends(verify_api_key)):
    """获取所有任务数据"""
    return {
        "success": True,
        "tasks": tasks_store
    }

# 新增：获取特定任务数据的路由
@api_router.get("/tasks/{task_id}", response_model=Dict[str, Any])
async def get_task(task_id: str, token: str = Depends(verify_api_key)):
    """获取特定任务数据"""
    if task_id not in tasks_store:
        return {
            "success": False,
            "error": f"Task not found: {task_id}"
        }
    
    return {
        "success": True,
        "task": tasks_store[task_id]
    }

# 新增：HTML页面路由，用于展示审核数据
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """审核数据展示页面"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>GoHumanLoop 审核数据展示</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 20px;
                background-color: #f5f5f5;
            }
            .container {
                max-width: 1200px;
                margin: 0 auto;
                background-color: white;
                padding: 20px;
                border-radius: 5px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            }
            h1 {
                color: #333;
                border-bottom: 1px solid #eee;
                padding-bottom: 10px;
            }
            .task-list {
                margin-bottom: 20px;
            }
            .task-item {
                background-color: #f9f9f9;
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 15px;
                margin-bottom: 15px;
            }
            .task-header {
                display: flex;
                justify-content: space-between;
                margin-bottom: 10px;
                font-weight: bold;
            }
            .conversation-list {
                margin-left: 20px;
            }
            .conversation-item {
                background-color: #fff;
                border: 1px solid #eee;
                border-radius: 4px;
                padding: 10px;
                margin-bottom: 10px;
            }
            .request-list {
                margin-left: 20px;
            }
            .request-item {
                background-color: #f5f5f5;
                border: 1px solid #eee;
                border-radius: 4px;
                padding: 10px;
                margin-bottom: 10px;
            }
            .status-approved {
                color: green;
                font-weight: bold;
            }
            .status-rejected {
                color: red;
                font-weight: bold;
            }
            .status-pending {
                color: orange;
                font-weight: bold;
            }
            .status-completed {
                color: blue;
                font-weight: bold;
            }
            .status-cancelled {
                color: gray;
                font-weight: bold;
            }
            .refresh-btn {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 10px 15px;
                text-align: center;
                text-decoration: none;
                display: inline-block;
                font-size: 16px;
                margin: 10px 0;
                cursor: pointer;
                border-radius: 4px;
            }
            pre {
                background-color: #f5f5f5;
                padding: 10px;
                border-radius: 4px;
                overflow-x: auto;
            }
            .empty-message {
                text-align: center;
                padding: 20px;
                color: #666;
            }
            .api-key-form {
                margin-bottom: 20px;
                display: flex;
                align-items: center;
            }
            .api-key-form input {
                padding: 8px;
                margin-right: 10px;
                border: 1px solid #ddd;
                border-radius: 4px;
                flex-grow: 1;
            }
            .api-key-form button {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 15px;
                cursor: pointer;
                border-radius: 4px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>GoHumanLoop 审核数据展示</h1>
            
            <div class="api-key-form">
                <input type="text" id="apiKey" placeholder="输入API密钥" value="gohumanloop">
                <button onclick="setApiKey()">设置API密钥</button>
            </div>
            
            <button class="refresh-btn" onclick="loadTasks()">刷新数据</button>
            
            <div id="taskList" class="task-list">
                <div class="empty-message">加载中...</div>
            </div>
        </div>

        <script>
            let apiKey = 'gohumanloop';
            
            function setApiKey() {
                apiKey = document.getElementById('apiKey').value;
                loadTasks();
            }
            
            function loadTasks() {
                const taskList = document.getElementById('taskList');
                taskList.innerHTML = '<div class="empty-message">加载中...</div>';
                
                fetch('/api/v1/humanloop/tasks', {
                    headers: {
                        'Authorization': `Bearer ${apiKey}`
                    }
                })
                .then(response => {
                    if (!response.ok) {
                        throw new Error('API请求失败');
                    }
                    return response.json();
                })
                .then(data => {
                    if (data.success && Object.keys(data.tasks).length > 0) {
                        let html = '';
                        
                        for (const [taskId, taskInfo] of Object.entries(data.tasks)) {
                            const taskData = taskInfo.data;
                            const receivedAt = new Date(taskInfo.received_at).toLocaleString();
                            
                            html += `
                                <div class="task-item">
                                    <div class="task-header">
                                        <span>任务ID: ${taskId}</span>
                                        <span>接收时间: ${receivedAt}</span>
                                    </div>
                                    <div class="conversation-list">
                            `;
                            
                            if (taskData.conversations && taskData.conversations.length > 0) {
                                taskData.conversations.forEach(conversation => {
                                    html += `
                                        <div class="conversation-item">
                                            <div>对话ID: ${conversation.conversation_id}</div>
                                            <div>提供者: ${conversation.provider_id || '未知'}</div>
                                            <div class="request-list">
                                    `;
                                    
                                    if (conversation.requests && conversation.requests.length > 0) {
                                        conversation.requests.forEach(request => {
                                            let statusClass = '';
                                            switch(request.status) {
                                                case 'approved': statusClass = 'status-approved'; break;
                                                case 'rejected': statusClass = 'status-rejected'; break;
                                                case 'pending': statusClass = 'status-pending'; break;
                                                case 'completed': statusClass = 'status-completed'; break;
                                                case 'cancelled': statusClass = 'status-cancelled'; break;
                                                default: statusClass = '';
                                            }
                                            
                                            html += `
                                                <div class="request-item">
                                                    <div>请求ID: ${request.request_id}</div>
                                                    <div>类型: ${request.loop_type}</div>
                                                    <div>状态: <span class="${statusClass}">${request.status}</span></div>
                                            `;
                                            
                                            if (request.responded_by) {
                                                html += `<div>响应者: ${request.responded_by}</div>`;
                                            }
                                            
                                            if (request.responded_at) {
                                                html += `<div>响应时间: ${new Date(request.responded_at).toLocaleString()}</div>`;
                                            }
                                            
                                            if (request.response) {
                                                html += `
                                                    <div>响应内容:
                                                        <pre>${JSON.stringify(request.response, null, 2)}</pre>
                                                    </div>
                                                `;
                                            }
                                            
                                            if (request.error) {
                                                html += `<div>错误: ${request.error}</div>`;
                                            }
                                            
                                            html += `</div>`;
                                        });
                                    } else {
                                        html += `<div>无请求数据</div>`;
                                    }
                                    
                                    html += `
                                            </div>
                                        </div>
                                    `;
                                });
                            } else {
                                html += `<div>无对话数据</div>`;
                            }
                            
                            html += `
                                    </div>
                                </div>
                            `;
                        }
                        
                        taskList.innerHTML = html;
                    } else {
                        taskList.innerHTML = '<div class="empty-message">暂无任务数据</div>';
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    taskList.innerHTML = `<div class="empty-message">加载失败: ${error.message}</div>`;
                });
            }
            
            // 页面加载时自动加载任务数据
            document.addEventListener('DOMContentLoaded', loadTasks);
            
            // 每30秒自动刷新一次
            setInterval(loadTasks, 30000);
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

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