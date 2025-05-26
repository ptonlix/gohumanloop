"""
LangGraph 与 GoHumanLoop 简单集成示例

这是一个最小化示例，展示如何在 LangGraph 中使用 GoHumanLoopManager 和 LangGraphAdapter
进行人机交互。

配置：
- API 地址: http://localhost:8000/api
- API KEY: gohumanloop
"""

import os
import time
from typing import TypedDict, List, Dict, Any
from dotenv import load_dotenv

# 导入 LangGraph 相关库
from langgraph.graph import StateGraph, END

# 导入 GoHumanLoop 相关库
from gohumanloop.manager.ghl_manager import GoHumanLoopManager
from gohumanloop.adapters.langgraph_adapter import HumanloopAdapter
from gohumanloop.core.interface import HumanLoopStatus

import logging

logging.basicConfig(level=logging.INFO)

# 设置环境变量
os.environ["GOHUMANLOOP_API_KEY"] = "gohumanloop"
os.environ["GOHUMANLOOP_API_BASE_URL"] = "http://localhost:8000/api"


# 定义简单状态类型
class SimpleState(TypedDict):
    messages: List[Dict[str, str]]
    approval_result: Dict[str, Any]


# 创建 GoHumanLoopManager 实例
manager = GoHumanLoopManager()

# 创建 LangGraphAdapter 实例
adapter = HumanloopAdapter(
    manager=manager,
    default_timeout=300,  # 默认超时时间为5分钟
)


# 定义需要人工审批的节点
@adapter.require_approval(
    task_id="simple-approval-test",
    additional="这是一个简单的审批示例。",
    execute_on_reject=True,
)
def human_approval_node(state: SimpleState, approval_result=None) -> SimpleState:
    """需要人工审批的节点"""
    print("等待人工审批中...")

    # 处理审批结果
    if approval_result:
        status = approval_result.get("status")
        response = approval_result.get("response", {})

        if status == HumanLoopStatus.APPROVED:
            state["messages"].append(
                {
                    "role": "human",
                    "content": f"审批已通过！理由: {response.get('reason', '未提供')}",
                }
            )
        elif status == HumanLoopStatus.REJECTED:
            state["messages"].append(
                {
                    "role": "human",
                    "content": f"审批被拒绝。理由: {response.get('reason', '未提供')}",
                }
            )

    return state


def final_node(state: SimpleState) -> SimpleState:
    """最终节点"""
    state["messages"].append({"role": "system", "content": "工作流程已完成！"})
    return state


# 构建工作流图
def build_simple_graph():
    """构建简单工作流图"""
    graph = StateGraph(SimpleState)

    # 添加节点
    graph.add_node("human_approval", human_approval_node)
    graph.add_node("final", final_node)

    # 设置边
    graph.add_edge("human_approval", "final")
    graph.add_edge("final", END)

    # 设置入口
    graph.set_entry_point("human_approval")

    return graph.compile()


# 运行工作流
def run_simple_workflow():
    """运行简单工作流"""
    with adapter:
        # 构建工作流图
        workflow = build_simple_graph()

        # 初始化状态
        initial_state = SimpleState(
            messages=[{"role": "system", "content": "开始简单工作流..."}],
            approval_result={},
        )

        # 运行工作流
        for output in workflow.stream(initial_state, stream_mode="values"):
            print(f"状态: {output}")

            # 等待一下，便于观察
            time.sleep(1)


# 主函数
if __name__ == "__main__":
    # 加载环境变量
    load_dotenv()

    # 运行工作流
    run_simple_workflow()
