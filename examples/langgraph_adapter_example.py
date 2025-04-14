from gohumanloop.adapters.langgraph_adapter import LangGraphAdapter
from gohumanloop.core.manager import DefaultHumanLoopManager
from gohumanloop.providers.terminal_provider import TerminalProvider

# 创建 HumanLoopManager 实例
manager = DefaultHumanLoopManager(default_provider=TerminalProvider())

# 创建 LangGraphAdapter 实例
adapter = LangGraphAdapter(manager, default_timeout=60)

# 示例1: 使用审批装饰器
@adapter.require_approval(
    task_id="sensitive_operation",
    conversation_id="conv_001"
)
def perform_sensitive_operation(amount: float) -> str:
    """执行一个需要人工审批的敏感操作
    
    Args:
        amount: 操作金额
        
    Returns:
        str: 操作结果
    """
    return f"Successfully processed amount: {amount}"

# 示例2: 使用信息获取装饰器
@adapter.require_info(
    task_id="user_feedback",
    conversation_id="conv_002",
    ret_key="user_input"
)
def process_user_feedback(data: dict, user_input: str = "") -> str:
    """处理用户反馈信息
    
    Args:
        data: 原始数据
        user_input: 从人工获取的输入信息
        
    Returns:
        str: 处理结果
    """
    return f"Processed feedback: {data} with user input: {user_input}"

def main():
    # 测试审批场景
    # try:
    #     result = perform_sensitive_operation(1000.0)
    #     print("审批结果:", result)
    # except Exception as e:
    #     print("审批错误:", str(e))
    
    # 测试信息获取场景
    try:
        result = process_user_feedback({"type": "bug_report"})
        print("信息处理结果:", result)
    except Exception as e:
        print("信息处理错误:", str(e))

if __name__ == "__main__":
    main()