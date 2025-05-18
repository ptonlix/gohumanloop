import asyncio
import json
import sys
from gohumanloop.core.interface import HumanLoopStatus, HumanLoopType
from gohumanloop.providers.terminal_provider import TerminalProvider


async def example_usage():
    """示例：如何使用终端提供者"""
    print("=== 终端提供者使用示例 ===")
    
    # 创建终端提供者
    provider = TerminalProvider(name="example_provider")
    
    # 选择要运行的示例
    print("\n请选择要运行的示例:")
    print("1. 审批请求示例")
    print("2. 对话交互示例")
    print("3. 信息收集示例")
    print("4. 运行所有示例")
    
    choice = input("\n请输入选项 (1-4): ").strip()
    
    if choice == "1" or choice == "4":
        await run_approval_example(provider)
    
    if choice == "2" or choice == "4":
        await run_conversation_example(provider)
    
    if choice == "3" or choice == "4":
        await run_information_example(provider)
    
    print("\n=== 示例结束 ===")


async def run_approval_example(provider):
    """运行审批请求示例"""
    print("\n[示例1] 发起审批请求...")
    approval_result = await provider.async_request_humanloop(
        task_id="task_123",
        conversation_id="conv_456",
        loop_type=HumanLoopType.APPROVAL,
        context={"message": "请审批以下内容：\n1. 购买新的服务器\n2. 升级现有系统", "question":"Please review and approve/reject this human loop execution."}
    )
    
    # 等待用户完成交互
    print("\n等待用户完成审批交互...")
    while True:
        await asyncio.sleep(2)
        status = await provider.async_check_request_status(
            conversation_id="conv_456",
            request_id=approval_result.request_id
        )
        if status.status != HumanLoopStatus.PENDING and status.status != HumanLoopStatus.INPROGRESS:
            break
    
    print(f"\n[示例1] 审批请求完成，状态: {status.status.value}")
    if status.response:
        print(f"响应内容: {json.dumps(status.response, ensure_ascii=False)}")

    # 获取所有对话记录
    conversation_history = provider.async_get_conversation_history("conv_456")
    print("\n完整对话记录:")
    for entry in conversation_history:
        print(f"时间: {entry['responded_at']}")
        print(f"状态: {entry['status']}")
        print(f"请求上下文: {entry['context']}")
        print(f"响应: {json.dumps(entry['response'], ensure_ascii=False)}")
        print("---")


async def run_conversation_example(provider):
    """运行对话交互示例"""
    print("\n[示例2] 发起对话请求...")
    conversation_result = await provider.async_request_humanloop(
        task_id="task_789",
        conversation_id="conv_789",
        loop_type=HumanLoopType.CONVERSATION,
        context={"message": "您好，我是AI助手，有什么可以帮您的吗？"}
    )
    
    # 等待用户完成第一轮对话
    print("\n等待用户完成第一轮对话...")
    while True:
        await asyncio.sleep(2)
        status = await provider.async_check_request_status(
            conversation_id="conv_789",
            request_id=conversation_result.request_id
        )
        
        # 如果状态已完成，则退出循环
        if status.status == HumanLoopStatus.COMPLETED:
            break
            
        # 如果状态是进行中，且已有响应，则继续对话
        if status.status == HumanLoopStatus.INPROGRESS and status.response:
            print("\n[示例2] 继续对话...")
            conversation_result = await provider.async_continue_humanloop(
                conversation_id="conv_789",
                context={"message": "感谢您的回复，还有其他问题吗？"}
            )
    
    # 获取所有对话记录
    conversation_history = provider.async_get_conversation_history("conv_789")
    print("\n完整对话记录:")
    for entry in conversation_history:
        print(f"时间: {entry['responded_at']}")
        print(f"状态: {entry['status']}")
        print(f"请求上下文: {entry['context']}")
        print(f"响应: {json.dumps(entry['response'], ensure_ascii=False)}")
        print("---")


async def run_information_example(provider):
    """运行信息收集示例"""
    print("\n[示例3] 发起信息收集请求...")
    info_result = await provider.async_request_humanloop(
        task_id="task_info",
        conversation_id="conv_info",
        loop_type=HumanLoopType.INFORMATION,
        context={"message": "请提供您的联系方式以便我们进一步沟通",  "question": "Please provide the required information for the human loop",}
    )
    
    # 等待用户完成信息提供
    print("\n等待用户提供信息...")
    while True:
        await asyncio.sleep(2)
        status = await provider.async_check_request_status(
            conversation_id="conv_info",
            request_id=info_result.request_id
        )
        if status.status != HumanLoopStatus.PENDING and status.status != HumanLoopStatus.INPROGRESS:
            break
    
    print(f"\n[示例3] 信息收集完成，状态: {status.status.value}")
    if status.response:
        print(f"响应内容: {json.dumps(status.response, ensure_ascii=False)}")


if __name__ == "__main__":
    try:
        asyncio.run(example_usage())
    except KeyboardInterrupt:
        print("\n程序被用户中断")
    except Exception as e:
        print(f"\n运行示例时出错: {e}")