"""
APIProvider Mock 使用示例

本示例展示了如何使用 APIProvider 与 Mock 服务进行三种不同类型的人机交互：
1. 审批场景 - 请求人类审批某项操作
2. 获取信息场景 - 请求人类提供特定信息
3. 多轮对话场景 - 与人类进行多轮对话交互
4. 取消请求场景 - 取消正在进行的人机交互请求
5. 取消对话场景 - 取消整个对话的所有请求
"""

import asyncio
import os
import uuid
import json
from dotenv import load_dotenv
from gohumanloop.utils import get_secret_from_env

from gohumanloop.providers.api_provider import APIProvider
from gohumanloop.core.interface import HumanLoopType, HumanLoopStatus

async def approval_example(provider):
    """
    审批场景示例 - 请求人类审批某项操作
    """
    print("\n=== 审批场景示例 ===")
    
    # 构建上下文信息
    context = { 
        "message": {
        "操作": "系统配置变更",
        "描述": "需要更新生产环境的配置参数，调整缓存策略以提高系统响应速度",
        "影响": "此变更可能导致短暂的服务波动，约1分钟",
        "计划执行时间": "2024-05-20 02:00 UTC",
        "回滚计划": "如果出现问题，将立即恢复原始配置参数"
        },
        "question": "请审批该系统配置变更",
    }
    
    # 发起审批请求
    result = await provider.request_humanloop(
        task_id="SYS-CONFIG-001",
        conversation_id="approval-example-1",
        loop_type=HumanLoopType.APPROVAL,
        context=context,
        metadata={
            "platform": "mock",
            "subject": f"[测试] 系统配置变更审批请求 {str(uuid.uuid4())}"
        },
        timeout=3600  # 1小时超时
    )
    
    print(f"请求已发送，状态: {result.status}")
    print(f"请求ID: {result.request_id}")
    
    # 等待并检查结果
    while True:
        await asyncio.sleep(5)  # 每5秒检查一次
        status = await provider.check_request_status(
            conversation_id=result.conversation_id,
            request_id=result.request_id
        )
        if status.status != HumanLoopStatus.PENDING:
            print(f"收到回复，状态: {status.status}")
            if status.status == HumanLoopStatus.APPROVED:
                print("审批已通过!")
                if status.response and "decision" in status.response:
                    print(f"决定: {status.response['decision']}")
                if status.response and "reason" in status.response:
                    print(f"理由: {status.response['reason']}")
            elif status.status == HumanLoopStatus.REJECTED:
                print("审批被拒绝!")
                if status.response and "decision" in status.response:
                    print(f"决定: {status.response['decision']}")
                if status.response and "reason" in status.response:
                    print(f"理由: {status.response['reason']}")
            elif status.status == HumanLoopStatus.ERROR:
                print(f"发生错误: {status.error}")
            break
        
        print("等待回复中...")

async def information_example(provider):
    """
    获取信息场景示例 - 请求人类提供特定信息
    """
    print("\n=== 获取信息场景示例 ===")
    
    # 构建上下文信息
    context = {
        "message":{
        "项目": "产品功能规划",
        "需要信息": "请提供下一季度产品路线图的优先级排序和预期交付时间",
        "用途": "此信息将用于团队资源分配和sprint规划",
        "截止日期": "2024-05-25"
         },
        "question": "请提供产品路线图信息"
    }
    
    # 发起信息请求
    result = await provider.request_humanloop(
        task_id="INFO-REQ-002",
        conversation_id="info-example-1",
        loop_type=HumanLoopType.INFORMATION,
        context=context,
        metadata={
            "platform": "mock",
            "subject": f"[测试] 请提供产品路线图信息 {str(uuid.uuid4())}"
        },
        timeout=7200  # 2小时超时
    )
    
    print(f"请求已发送，状态: {result.status}")
    print(f"请求ID: {result.request_id}")
    
    # 等待并检查结果
    while True:
        await asyncio.sleep(5)  # 每5秒检查一次
        status = await provider.check_request_status(
            conversation_id=result.conversation_id,
            request_id=result.request_id
        )
        
        if status.status != HumanLoopStatus.PENDING:
            print(f"收到回复，状态: {status.status}")
            if status.status == HumanLoopStatus.COMPLETED:
                print("已收到信息!")
                if status.response:
                    if "information" in status.response:
                        print(f"提供的信息: {status.response['information']}")
            elif status.status == HumanLoopStatus.ERROR:
                print(f"发生错误: {status.error}")
            break
        
        print("等待回复中...")

async def conversation_example(provider):
    """
    多轮对话场景示例 - 与人类进行多轮对话交互
    """
    print("\n=== 多轮对话场景示例 ===")
    
    # 初始上下文信息
    context = {
        "message":{
        "主题": "用户体验改进讨论",
        "背景": "我们收到了一些用户反馈，指出当前应用的导航结构不够直观，需要讨论改进方案",
        },
        "question": "请提供您对改进导航结构的建议。"
    }
    
    # 发起对话
    result = await provider.request_humanloop(
        task_id="CONV-003",
        conversation_id="conv-example-1",
        loop_type=HumanLoopType.CONVERSATION,
        context=context,
        metadata={
            "platform": "mock",
            "subject": f"[测试] 用户体验改进讨论 {str(uuid.uuid4())}"
        }
    )
    
    print(f"对话已开始，状态: {result.status}")
    print(f"请求ID: {result.request_id}")
    
    # 第一轮对话
    first_response = None
    while True:
        await asyncio.sleep(5)  # 每5秒检查一次
        status = await provider.check_request_status(
            conversation_id=result.conversation_id,
            request_id=result.request_id
        )
        
        if status.status not in [HumanLoopStatus.PENDING]:
            print(f"收到回复，状态: {status.status}")
            if status.status == HumanLoopStatus.INPROGRESS:
                if status.response and "message" in status.response:
                    first_response = status.response["message"]
                    print(f"人类回复: {first_response[:100]}...")  # 只显示前100个字符
                    break

            elif status.status == HumanLoopStatus.COMPLETED:
                if status.response and "message" in status.response:
                    first_response = status.response["message"]
                    print(f"人类回复: {first_response[:100]}...")  # 只显示前100个字符
                    print("对话已结束")
                    return 

            elif status.status == HumanLoopStatus.ERROR:
                print(f"发生错误: {status.error}")
                return
        
        print("等待回复中...")
    
    # 继续对话 - 第二轮
    if first_response:
        # 构建新的上下文，包含对第一轮回复的响应
        follow_up_context = {
            "message":{
            "上一轮讨论": first_response[:100] + "...",  # 简化显示
            "后续问题": "感谢您的建议！您能否详细说明如何实现这些改进，以及预期的用户反应会是什么？"
            },
            "question": "请继续讨论。"
        }
        
        # 继续对话
        continue_result = await provider.continue_humanloop(
            conversation_id=result.conversation_id,
            context=follow_up_context,
            metadata={
                "platform": "mock"
            }
        )
        
        print("\n已发送后续问题，等待回复...")
        
        # 等待第二轮回复
        while True:
            await asyncio.sleep(5)
            status = await provider.check_request_status(
                conversation_id=continue_result.conversation_id,
                request_id=continue_result.request_id
            )
            
            if status.status not in [HumanLoopStatus.PENDING]:
                print(f"收到回复，状态: {status.status}")
                if status.status == HumanLoopStatus.INPROGRESS:
                    if status.response and "message" in status.response:
                        follow_response = status.response["message"]
                        print(f"人类回复: {follow_response[:100]}...")  # 只显示前100个字符
                        print("可以继续对话")
                        # 构建新的上下文，包含对第二轮回复的响应
                        follow_up_context = {
                            "message":{
                            "上一轮讨论": follow_response[:100] + "...",  # 简化显示
                            "后续问题": "非常感谢您的详细说明！您认为实施这些改进需要多长时间？还有其他需要考虑的因素吗？"
                            },
                            "question": "请继续讨论。"
                        }
                        
                        # 继续对话
                        continue_result = await provider.continue_humanloop(
                            conversation_id=result.conversation_id,
                            context=follow_up_context,
                            metadata={
                                "platform": "mock"
                            }
                        )
                elif status.status == HumanLoopStatus.COMPLETED:
                    follow_response = status.response["message"]
                    print(f"人类回复: {follow_response[:100]}...")  # 只显示前100个字符
                    print("对话已结束")
                    break
                elif status.status == HumanLoopStatus.ERROR:
                    print(f"发生错误: {status.error}")
            
            print("等待回复中...")

async def cancel_request_example(provider):
    """
    取消请求场景示例 - 取消正在进行的人机交互请求
    """
    print("\n=== 取消请求场景示例 ===")
    
    # 构建上下文信息
    context = { 
        "message": {
        "操作": "系统维护通知",
        "描述": "计划对系统进行例行维护，可能导致服务短暂不可用",
        "影响": "维护期间用户可能无法访问系统，预计持续30分钟",
        "计划执行时间": "2024-05-25 03:00 UTC",
        "备注": "如有异议，请及时回复"
        },
        "question": "请审批该系统维护计划",
    }
    
    # 发起审批请求
    result = await provider.request_humanloop(
        task_id="SYS-MAINT-001",
        conversation_id="cancel-request-example-1",
        loop_type=HumanLoopType.APPROVAL,
        context=context,
        metadata={
            "platform": "mock",
            "subject": f"[测试] 系统维护通知审批请求 {str(uuid.uuid4())}"
        },
        timeout=3600  # 1小时超时
    )
    
    print(f"请求已发送，状态: {result.status}")
    print(f"请求ID: {result.request_id}")
    
    # 等待5秒后取消请求
    print("等待5秒后将取消请求...")
    await asyncio.sleep(5)
    
    # 取消请求
    cancel_success = await provider.cancel_request(
        conversation_id=result.conversation_id,
        request_id=result.request_id
    )
    
    if cancel_success:
        print("请求已成功取消!")
    else:
        print("请求取消失败!")
    
    # 检查请求状态
    status = await provider.check_request_status(
        conversation_id=result.conversation_id,
        request_id=result.request_id
    )
    
    print(f"请求状态: {status.status}")
    
    return result

async def cancel_conversation_example(provider):
    """
    取消对话场景示例 - 取消整个对话的所有请求
    """
    print("\n=== 取消对话场景示例 ===")
    
    conversation_id = f"cancel-conv-example-{str(uuid.uuid4())[:8]}"
    
    # 第一个请求：审批类型
    context1 = { 
        "message": {
        "操作": "数据库备份策略调整",
        "描述": "增加备份频率，从每日一次调整为每6小时一次",
        "影响": "可能导致备份期间数据库性能略有下降",
        "计划执行时间": "2024-05-26 00:00 UTC"
        },
        "question": "请审批该备份策略调整",
    }
    
    # 发起第一个请求
    result1 = await provider.request_humanloop(
        task_id="DB-BACKUP-001",
        conversation_id=conversation_id,
        loop_type=HumanLoopType.APPROVAL,
        context=context1,
        metadata={
            "platform": "mock",
            "subject": f"[测试] 数据库备份策略调整审批 {str(uuid.uuid4())}"
        }
    )
    
    print(f"第一个请求已发送，请求ID: {result1.request_id}")
    
    # 等待2秒后发送第二个请求
    await asyncio.sleep(2)
    
    # 第二个请求：信息类型
    context2 = {
        "message":{
        "项目": "数据库性能评估",
        "需要信息": "请提供当前数据库平均查询响应时间和高峰期并发连接数",
        "用途": "用于评估新备份策略对性能的影响",
        "截止日期": "2024-05-25"
        },
        "question": "请提供数据库性能信息"
    }
    
    # 发起第二个请求
    result2 = await provider.request_humanloop(
        task_id="DB-PERF-002",
        conversation_id=conversation_id,
        loop_type=HumanLoopType.INFORMATION,
        context=context2,
        metadata={
            "platform": "mock",
            "subject": f"[测试] 请提供数据库性能信息 {str(uuid.uuid4())}"
        }
    )
    
    print(f"第二个请求已发送，请求ID: {result2.request_id}")
    
    # 等待3秒后取消整个对话
    print("等待3秒后将取消整个对话...")
    await asyncio.sleep(3)
    
    # 取消整个对话
    cancel_success = await provider.cancel_conversation(
        conversation_id=conversation_id
    )
    
    if cancel_success:
        print("对话已成功取消!")
    else:
        print("对话取消失败!")
    
    await asyncio.sleep(3)
    # 检查两个请求的状态
    status1 = await provider.check_request_status(
        conversation_id=conversation_id,
        request_id=result1.request_id
    )
    
    status2 = await provider.check_request_status(
        conversation_id=conversation_id,
        request_id=result2.request_id
    )
    
    print(f"第一个请求状态: {status1.status}")
    print(f"第二个请求状态: {status2.status}")
    
    return conversation_id

async def main():
    
    # 加载环境变量
    load_dotenv()

    """主函数"""
    # 从环境变量获取API配置
    api_base_url = os.environ.get("API_BASE_URL", "http://localhost:8000/api")
    api_key = get_secret_from_env("GOHUMANLOOP_API_KEY", "gohumanloop")
    
    # 创建 APIProvider 实例
    provider = APIProvider(
        name="MockHumanLoop",
        api_base_url=api_base_url,
        api_key=api_key,
        default_platform="mock",
        poll_interval=5,  # 每5秒检查一次状态
    )
    
    # 运行示例
    example_type = input("请选择要运行的示例 (1: 审批, 2: 获取信息, 3: 多轮对话, 4: 取消请求, 5: 取消对话): ")
    
    if example_type == "1":
        await approval_example(provider)
    elif example_type == "2":
        await information_example(provider)
    elif example_type == "3":
        await conversation_example(provider)
    elif example_type == "4":
        await cancel_request_example(provider)
    elif example_type == "5":
        await cancel_conversation_example(provider)
    else:
        print("无效的选择，请输入1、2、3、4或5")

if __name__ == "__main__":
    # 运行主函数
    asyncio.run(main())