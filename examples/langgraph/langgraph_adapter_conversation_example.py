"""
LangGraph框架中使用require_conversation装饰器的简化示例

本示例展示了如何在LangGraph工作流中集成人机交互，
实现一个简单的问答助手，能够在关键决策点引入人类反馈。
"""
import os
from dotenv import load_dotenv
from typing import TypedDict, Annotated, Sequence, Dict, Any
import asyncio

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, human
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END

# 导入gohumanloop相关模块
from gohumanloop.core.interface import HumanLoopStatus
from gohumanloop.core.manager import DefaultHumanLoopManager
from gohumanloop.providers.terminal_provider import TerminalProvider
from gohumanloop.adapters.langgraph_adapter import HumanloopAdapter


# 定义工作流状态类型
class AgentState(TypedDict):
    messages: Annotated[Sequence[Any], "对话历史"]
    draft_response: Annotated[Dict[str, Any], "AI草拟的回复"]
    next_step: Annotated[str, "下一步操作"]
    feedback_history: Annotated[list, "人类反馈历史"]
    is_final: Annotated[bool, "是否为最终回复"]


# 初始化人机循环管理器和适配器
cli_provider = TerminalProvider(name="cli_provider")
manager = DefaultHumanLoopManager(cli_provider)
adapter = HumanloopAdapter(manager, default_timeout=300)

# 加载环境变量
load_dotenv()

# 从环境变量获取API密钥和基础URL
api_key = os.getenv("OPENAI_API_KEY")
api_base = os.getenv("OPENAI_API_BASE")

# 创建 LLM
llm = ChatOpenAI(model="deepseek-chat", base_url=api_base)


# 定义工作流节点
def initialize_state() -> AgentState:
    """初始化工作流状态"""
    return {
        "messages": [
            SystemMessage(content="你是一个专业的问答助手，负责提供准确、有用的信息。"),
        ],
        "draft_response": {},
        "next_step": "generate_response",
        "feedback_history": [],
        "is_final": False,
    }


def generate_response(state: AgentState) -> AgentState:
    """生成回复草稿"""
    messages = state["messages"]
    feedback_history = state["feedback_history"]

    # 如果有反馈历史，将其添加到消息中以改进回复
    if feedback_history:
        # 创建一个临时消息列表，包含原始消息和最新的反馈
        temp_messages = list(messages)
        last_feedback = feedback_history[-1]
        temp_messages.append(
            HumanMessage(content=f"请根据以下反馈调整你的回复: {last_feedback}")
        )
    else:
        temp_messages = messages

    # 使用LLM生成回复
    response = llm.invoke(temp_messages)

    # 更新状态
    draft_response = {
        "content": response.content,
        "iteration": len(feedback_history) + 1,
    }

    return {**state, "draft_response": draft_response, "next_step": "review_response"}


@adapter.require_conversation(
    task_id="simple_qa_task",
    conversation_id="response_review",
    state_key="draft_response",
    ret_key="human_feedback",
    additional="请审核AI生成的回复，并提供反馈或修改建议。",
)
def review_response(
    state: AgentState, human_feedback: Dict[str, Any] = {}
) -> AgentState:
    """审核回复，需要人类反馈"""
    messages = state["messages"]
    draft = state["draft_response"]
    feedback_history = state["feedback_history"].copy()
    is_final = False

    # 检查是否有人类反馈
    if human_feedback and human_feedback.get("status") == HumanLoopStatus.COMPLETED:
        # 人类满意，将草稿添加到消息历史并标记为最终版本
        messages.append(AIMessage(content=draft["content"]))
        is_final = True
    elif human_feedback and human_feedback.get("response"):
        feedback = human_feedback["response"]
        # 人类不满意，记录反馈并准备重新生成
        feedback_history.append(feedback)
    else:
        # 无人类反馈，默认通过
        messages.append(AIMessage(content=draft["content"]))
        is_final = True

    # 确定下一步
    next_step = END if is_final else "generate_response"

    return {
        **state,
        "messages": messages,
        "feedback_history": feedback_history,
        "is_final": is_final,
        "next_step": next_step,
    }


# 决定下一步的路由函数
def decide_next_step(state: AgentState) -> str:
    """根据状态决定下一步操作"""
    if state["is_final"]:
        return END
    return state["next_step"]


# 构建工作流图
workflow = StateGraph(AgentState)

# 添加节点
workflow.add_node("generate_response", generate_response)
workflow.add_node("review_response", review_response)

# 添加边

# 设置入口节点
workflow.set_entry_point("generate_response")
workflow.add_edge("generate_response", "review_response")

# 添加条件边，支持循环
workflow.add_conditional_edges(
    "review_response",
    decide_next_step,
    {"generate_response": "generate_response", END: END},
)

# 编译工作流
app = workflow.compile()


# 运行示例
async def run_example():
    print("=== 简单问答助手示例 ===")
    print("这个示例展示了如何在LangGraph工作流中使用require_conversation装饰器")
    print("实现人机协作的问答流程。\n")
    print(
        "提示: 如果对AI回复满意，请回复'满意'或'通过'结束流程。否则提供具体反馈以改进回复。\n"
    )

    # 初始化状态
    state = initialize_state()

    # 添加用户问题
    state["messages"].append(
        HumanMessage(content="请解释量子计算的基本原理和潜在应用。")
    )

    # 运行工作流
    result = await app.ainvoke(state)

    # 打印最终结果
    print("\n=== 工作流执行结果 ===")
    for i, message in enumerate(result["messages"]):
        if isinstance(message, SystemMessage):
            continue
        role = "用户" if isinstance(message, HumanMessage) else "助手"
        print(f"{role}: {message.content}\n")

    print("=== 反馈历史 ===")
    if result["feedback_history"]:
        for i, feedback in enumerate(result["feedback_history"]):
            print(f"反馈 {i+1}: {feedback}")
    else:
        print("无反馈记录")


if __name__ == "__main__":
    asyncio.run(run_example())
