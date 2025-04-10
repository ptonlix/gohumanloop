import asyncio
from typing import Dict, Any, TypedDict, Annotated
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
import gohumanloop as ghl

# 定义状态类型
class AgentState(TypedDict):
    messages: list
    next_action: str
    approval_status: Dict[str, Any]

# 创建人机交互适配器
adapter = ghl.create_langgraph_adapter(
    provider=ghl.create_api_provider(api_key="your_api_key")
)

# 定义需要人类批准的节点
@adapter.requires_approval(
    context_extractor=lambda state: {
        "title": "执行敏感操作",
        "description": "Agent 请求执行以下操作",
        "action": state.get("next_action", "未知操作"),
        "messages": state.get("messages", [])
    },
    blocking=True
)
async def execute_sensitive_action(state: AgentState) -> AgentState:
    """执行需要人类批准的敏感操作"""
    # 这里是操作的实际逻辑
    state["messages"].append({
        "role": "system",
        "content": f"已执行操作: {state['next_action']}"
    })
    return state

# 定义其他节点
async def determine_next_action(state: AgentState) -> AgentState:
    """确定下一步操作"""
    # 这里是确定下一步操作的逻辑
    state["next_action"] = "删除生产数据库"
    return state

async def handle_rejection(state: AgentState) -> AgentState:
    """处理被拒绝的情况"""
    state["messages"].append({
        "role": "system",
        "content": "操作被人类拒绝，寻找替代方案"
    })
    return state

# 定义路由逻辑
def router(state: AgentState) -> str:
    """根据状态决定下一个节点"""
    if state.get("approval_rejected"):
        return "handle_rejection"
    elif state.get("approval_error"):
        return END
    else:
        return END

# 构建图
workflow = StateGraph(AgentState)
workflow.add_node("determine_next_action", determine_next_action)
workflow.add_node("execute_sensitive_action", execute_sensitive_action)
workflow.add_node("handle_rejection", handle_rejection)

# 添加边
workflow.add_edge("determine_next_action", "execute_sensitive_action")
workflow.add_edge("execute_sensitive_action", router)
workflow.add_edge("handle_rejection", END)

# 编译图
app = workflow.compile()

# 运行工作流
async def run_workflow():
    initial_state = AgentState(
        messages=[{"role": "user", "content": "执行数据库操作"}],
        next_action="",
        approval_status={}
    )
    result = await app.ainvoke(initial_state)
    return result

if __name__ == "__main__":
    asyncio.run(run_workflow())