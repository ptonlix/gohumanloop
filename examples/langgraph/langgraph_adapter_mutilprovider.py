from typing import Dict, Any, List, Annotated, TypedDict
import operator
import os
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

from gohumanloop.adapters.langgraph_adapter import HumanloopAdapter
from gohumanloop.manager.ghl_manager import GoHumanLoopManager
from gohumanloop.providers.terminal_provider import TerminalProvider
from gohumanloop.providers.email_provider import EmailProvider
from gohumanloop.core.interface import HumanLoopStatus
import logging
from typing_extensions import TypedDict

# 设置日志配置
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("langgraph_adapter")

# 加载环境变量
load_dotenv()


# 定义状态类型
class AgentState(TypedDict):
    messages: List[Any]
    next: str


# 从环境变量获取API密钥和基础URL
api_key = os.getenv("OPENAI_API_KEY")
api_base = os.getenv("OPENAI_API_BASE")
# 从环境变量获取邮箱配置
smtp_server = os.environ.get("SMTP_SERVER", "smtp.example.com")
smtp_port = int(os.environ.get("SMTP_PORT", "587"))
imap_server = os.environ.get("IMAP_SERVER", "imap.example.com")
imap_port = int(os.environ.get("IMAP_PORT", "993"))
recipient_email = os.environ.get("TEST_RECIPIENT_EMAIL", "your_email@example.com")


# 创建 LLM
llm = ChatOpenAI(model="deepseek-chat", base_url=api_base)

# 创建 HumanLoopManager 实例
manager = GoHumanLoopManager(
    additional_providers=[
        TerminalProvider(name="TerminalProvider"),
        EmailProvider(
            name="EmailProvider",
            smtp_server=smtp_server,
            smtp_port=smtp_port,
            imap_server=imap_server,
            imap_port=imap_port,
            check_interval=30,  # 每30秒检查一次邮件
            language="en",  # 支持中文模板切换
        ),
    ]
)

# 创建 LangGraphAdapter 实例
adapter = HumanloopAdapter(manager, default_timeout=600)


# 使用审批装饰器的敏感操作
@adapter.require_approval(execute_on_reject=True, provider_id="TerminalProvider")
def execute_financial_transaction(
    amount: float, account_id: str, approval_result=None
) -> Dict[str, Any]:
    """执行一个需要人工审批的金融交易

    Args:
        amount: 交易金额
        account_id: 账户ID
        approval_result: 审批结果信息

    Returns:
        Dict: 交易结果
    """
    logger.info(f"审批信息: {approval_result}")

    # 根据审批结果处理交易
    if approval_result and approval_result.get("status") == HumanLoopStatus.APPROVED:
        return {
            "status": "success",
            "message": f"成功执行金额为 {amount} 的交易到账户 {account_id}",
            "transaction_id": "tx_123456789",
        }
    else:
        return {
            "status": "cancelled",
            "message": f"交易已被拒绝并取消: 金额 {amount}, 账户 {account_id}",
            "transaction_id": None,
        }


# LangGraph 工作流节点
def agent(state: AgentState) -> AgentState:
    """AI 代理处理节点"""
    messages = state["messages"]

    # 添加系统提示，定义LLM的角色和任务
    if not any(msg.type == "system" for msg in messages):
        system_message = SystemMessage(
            content="""
你是一位专业的金融顾问助手，负责帮助用户处理金融交易请求。
你的职责包括：
1. 理解用户的金融交易需求
2. 提供专业的金融建议
3. 协助用户完成交易流程
4. 确保交易安全和合规

请根据用户的请求，提供清晰的交易建议和操作方案。你的回复将由人工审核后再执行。
"""
        )
        messages = [system_message] + messages

    # 为用户消息添加更明确的指令
    last_message = messages[-1]
    if isinstance(last_message, HumanMessage):
        # 保留原始用户消息
        user_content = last_message.content

        # 构建更详细的提示
        enhanced_prompt = f"""
用户请求: {user_content}

请分析这个金融交易请求并提供以下内容:
1. 交易类型和金额确认
2. 交易风险评估
3. 执行建议和注意事项
4. 是否建议执行此交易(是/否)及理由

请以专业金融顾问的身份回复，你的建议将被用于决定是否执行此交易。
"""
        # 替换最后一条消息
        messages = messages[:-1] + [HumanMessage(content=enhanced_prompt)]

    # 调用LLM获取响应
    response = llm.invoke(messages)

    # 恢复原始用户消息以保持对话连贯性
    if isinstance(last_message, HumanMessage):
        # 使用列表切片替换最后一个元素，避免直接赋值可能导致的问题
        messages = messages[:-1] + [last_message]

    return {"messages": messages + [response], "next": "human_review"}


@adapter.require_approval(
    ret_key="approval_data",
    execute_on_reject=True,
    provider_id="EmailProvider",
    metadata={"recipient_email": recipient_email},
)
def human_review(state: AgentState, approval_data=None) -> AgentState:
    """人工审核节点"""
    messages = state["messages"]
    last_message = messages[-1].content if messages else "无消息"

    logger.info(f"人工审核结果: {approval_data}")

    # 添加审核结果到消息
    if approval_data and approval_data.get("status") == HumanLoopStatus.APPROVED:
        review_message = HumanMessage(content=f"[已审核] {last_message}")
        return {"messages": messages + [review_message], "next": "process_transaction"}
    else:
        review_message = HumanMessage(content=f"[审核拒绝] 请重新生成回复")
        return {"messages": messages + [review_message], "next": "agent"}


def process_transaction(state: AgentState) -> AgentState:
    """处理交易节点"""
    messages = state["messages"]

    # 模拟交易处理
    transaction_result = execute_financial_transaction(
        amount=100.0, account_id="user_12345"
    )

    result_message = HumanMessage(content=f"交易结果: {transaction_result['message']}")
    return {"messages": messages + [result_message], "next": "collect_feedback"}


@adapter.require_info(ret_key="feedback_data", provider_id="TerminalProvider")
def collect_feedback(state: AgentState, feedback_data={}) -> AgentState:
    """收集用户反馈节点"""
    messages = state["messages"]

    logger.info(f"获取的反馈信息: {feedback_data}")

    feedback_message = HumanMessage(
        content=f"收到用户反馈: {feedback_data.get('response', '无反馈')}"
    )
    return {"messages": messages + [feedback_message], "next": END}


def router(state: AgentState) -> str:
    """路由节点，决定下一步执行哪个节点"""
    return state["next"]


def main():
    # 创建工作流图
    workflow = StateGraph(AgentState)

    # 添加节点
    workflow.add_node("agent", agent)
    workflow.add_node("human_review", human_review)
    workflow.add_node("process_transaction", process_transaction)
    workflow.add_node("collect_feedback", collect_feedback)

    # 设置边和路由
    workflow.set_entry_point("agent")
    workflow.add_edge("agent", "human_review")
    workflow.add_conditional_edges("human_review", router)
    workflow.add_conditional_edges("process_transaction", router)
    workflow.add_conditional_edges("collect_feedback", router)

    # 编译工作流
    app = workflow.compile()

    # 运行工作流
    try:
        # 创建一个更符合金融投资场景的初始状态
        initial_state = {
            "messages": [
                HumanMessage(
                    content="我想投资5万元购买一些低风险的基金产品，主要用于退休储蓄，期限大约10年。请给我一些建议？"
                )
            ],
            "next": "agent",
        }

        for state in app.stream(initial_state, stream_mode="values"):
            messages = state.get("messages", {})
            if messages:
                logger.info(f"当前状态: {state['next']}")
                logger.info(f"最新消息: {messages[-1].content}")

        logger.info("工作流执行完成!")
    except Exception as e:
        logger.exception(f"工作流执行错误: {str(e)}")


if __name__ == "__main__":
    main()
