from typing import TypedDict
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, END
import logging

from gohumanloop.core.interface import HumanLoopStatus
from gohumanloop.core.manager import DefaultHumanLoopManager
from gohumanloop.providers.terminal_provider import TerminalProvider
from gohumanloop.adapters.base_adapter import (
    HumanloopAdapter,
    AgentOpsHumanLoopCallback,
)
from dotenv import load_dotenv

# 配置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("gohumanloop.langgraph")
logger.setLevel(logging.INFO)

# 加载环境变量
load_dotenv()


# 定义工作流状态
class WorkflowState(TypedDict):
    input: str
    output: str
    approved: bool
    review_feedback: str


# 模拟一个 HumanLoopManager 实例
manager = DefaultHumanLoopManager(
    initial_providers=TerminalProvider(name="TerminalProvider")
)
adapter = HumanloopAdapter(manager)


# 定义工作流节点
@adapter.require_approval(
    callback=AgentOpsHumanLoopCallback(),
    ret_key="approval_info",
    execute_on_reject=True,
)
def review_output(state: WorkflowState, approval_info=None) -> WorkflowState:
    """审查输入的内容"""
    logger.info(f"开始审查输出 - 当前状态: {state}")

    if approval_info and approval_info.get("status") == HumanLoopStatus.APPROVED:
        state["approved"] = True
        state["review_feedback"] = approval_info.get("response", "")
    elif approval_info and approval_info.get("status") == HumanLoopStatus.REJECTED:
        state["approved"] = False
        state["review_feedback"] = approval_info.get("response", "")
        logger.info(f"审批未通过 - 反馈: {state['review_feedback']}")

    return state


def generate_output(state: WorkflowState) -> WorkflowState:
    """生成输出内容"""
    if state.get("review_feedback"):
        logger.info(f"审批反馈 - {state['review_feedback']}")
    state["input"] = input("请输入要审批的内容: ")
    state["output"] = state["input"]
    logger.info(f"通过审批的内容: {state['output']}")
    return state


def should_end(state: WorkflowState) -> bool:
    """判断是否结束工作流"""
    return state.get("approved", False)


# 构建工作流图
workflow = StateGraph(WorkflowState)

# 添加节点
workflow.add_node("generate", generate_output)
workflow.add_node("review", review_output)

# 设置边和条件
workflow.set_entry_point("generate")
workflow.add_edge("generate", "review")
workflow.add_conditional_edges(
    "review",
    should_end,
    {
        True: END,  # 如果审批通过，结束工作流
        False: "generate",  # 如果审批未通过，重新生成
    },
)

# 编译工作流
app = workflow.compile()


# 使用示例
async def run_workflow():
    logger.info("开始执行工作流")
    initial_state = WorkflowState(
        input="", output="", approved=False, review_feedback=""
    )

    try:
        final_state = await app.ainvoke(initial_state)
        logger.info(f"工作流执行完成 - 最终状态: {final_state}")
    except Exception as e:
        logger.error(f"工作流执行出错: {e}", exc_info=True)


if __name__ == "__main__":
    import asyncio

    asyncio.run(run_workflow())
