"""
EmailProvider 使用示例

本示例展示了如何使用 EmailProvider 进行三种不同类型的人机交互：
1. 审批场景 - 请求人类审批某项操作
2. 获取信息场景 - 请求人类提供特定信息
3. 多轮对话场景 - 与人类进行多轮对话交互
"""

import asyncio
import os
import uuid
from dotenv import load_dotenv
from datetime import datetime
from pydantic import SecretStr

from gohumanloop.providers.email_provider import EmailProvider
from gohumanloop.core.interface import HumanLoopType, HumanLoopStatus

async def approval_example(provider):
    """
    审批场景示例 - 请求人类审批某项操作
    """
    print("\n=== 审批场景示例 ===")
    
    # 构建上下文信息
    context = { 
        "message": {
        "操作": "数据库架构变更",
        "描述": "需要在用户表中添加新字段'user_preferences'，用于存储用户偏好设置",
        "影响": "此变更将导致系统停机约5分钟",
        "计划执行时间": "2023-12-15 03:00 UTC",
        "回滚计划": "如果出现问题，将通过备份恢复原始架构"
        },
        "question": "请审批该数据库架构变更",
    }
    
    # 发起审批请求
    result = await provider.async_request_humanloop(
        task_id="DB-CHANGE-001",
        conversation_id="approval-example-1",
        loop_type=HumanLoopType.APPROVAL,
        context=context,
        metadata={
            "recipient_email": os.environ.get("TEST_RECIPIENT_EMAIL", "your_email@example.com"),
            "subject": f"[测试] 数据库架构变更审批请求 {str(uuid.uuid4())}"
        },
        timeout=3600  # 1小时超时
    )
    
    print(f"请求已发送，状态: {result.status}")
    print(f"请求ID: {result.request_id}")
    
    # 等待并检查结果
    while True:
        await asyncio.sleep(10)  # 每10秒检查一次
        status = await provider.async_check_request_status(
            conversation_id=result.conversation_id,
            request_id=result.request_id
        )
        if status.status != HumanLoopStatus.PENDING:
            print(f"收到回复，状态: {status.status}")
            if status.status == HumanLoopStatus.APPROVED:
                print("审批已通过!")
                if status.response and "reason" in status.response:
                    print(f"理由: {status.response['reason']}")
            elif status.status == HumanLoopStatus.REJECTED:
                print("审批被拒绝!")
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
        "项目": "年度市场调研报告",
        "需要信息": "请提供2023年第四季度的销售数据和客户反馈摘要",
        "用途": "此信息将用于完成年度市场分析报告",
        "截止日期": "2023-12-20"
         },
        "question": "请提供2024年季度销售数据"
    }
    
    # 发起信息请求
    result = await provider.async_request_humanloop(
        task_id="INFO-REQ-002",
        conversation_id="info-example-1",
        loop_type=HumanLoopType.INFORMATION,
        context=context,
        metadata={
            "recipient_email": os.environ.get("TEST_RECIPIENT_EMAIL", "your_email@example.com"),
            "subject": f"[测试] 请提供2024年季度销售数据 {str(uuid.uuid4())}"
        },
        timeout=7200  # 2小时超时
    )
    
    print(f"请求已发送，状态: {result.status}")
    print(f"请求ID: {result.request_id}")
    
    # 等待并检查结果
    while True:
        await asyncio.sleep(10)  # 每10秒检查一次
        status = await provider.async_check_request_status(
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
        "主题": "产品功能讨论",
        "背景": "我们正在开发一个新的电子商务平台，需要讨论几个关键功能的实现方案",
        },
        "question": "请提供您的建议和理由。"
    }
    
    # 发起对话
    result = await provider.async_request_humanloop(
        task_id="CONV-003",
        conversation_id="conv-example-1",
        loop_type=HumanLoopType.CONVERSATION,
        context=context,
        metadata={
            "recipient_email": os.environ.get("TEST_RECIPIENT_EMAIL", "your_email@example.com"),
            "subject": f"[测试] 产品功能讨论 {str(uuid.uuid4())}"
        }
    )
    
    print(f"对话已开始，状态: {result.status}")
    print(f"请求ID: {result.request_id}")
    
    # 第一轮对话
    first_response = None
    while True:
        await asyncio.sleep(10)  # 每10秒检查一次
        status = await provider.async_check_request_status(
            conversation_id=result.conversation_id,
            request_id=result.request_id
        )
        
        if status.status not in [HumanLoopStatus.PENDING]:
            print(f"收到回复，状态: {status.status}")
            if status.status == HumanLoopStatus.INPROGRESS:
                if status.response and "user_content" in status.response:
                    first_response = status.response["user_content"]
                    print(f"人类回复: {first_response[:100]}...")  # 只显示前100个字符
                    break

            elif status.status == HumanLoopStatus.COMPLETED:
                if status.response and "user_content" in status.response:
                    first_response = status.response["user_content"]
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
            "后续问题": "感谢您的建议！关于您提到的功能，您认为实现这些功能的最大挑战是什么？我们应该如何克服这些挑战？"
            },
            "question": "请继续讨论。"
        }
        
        # 继续对话
        continue_result = await provider.async_continue_humanloop(
            conversation_id=result.conversation_id,
            context=follow_up_context,
            metadata={
                "recipient_email": os.environ.get("TEST_RECIPIENT_EMAIL", "your_email@example.com")
            }
        )
        
        print("\n已发送后续问题，等待回复...")
        
        # 等待第二轮回复
        while True:
            await asyncio.sleep(10)
            status = await provider.async_check_request_status(
                conversation_id=continue_result.conversation_id,
                request_id=continue_result.request_id
            )
            
            if status.status not in [HumanLoopStatus.PENDING]:
                print(f"收到回复，状态: {status.status}")
                if status.status == HumanLoopStatus.INPROGRESS:
                    if status.response and "user_content" in status.response:
                        follow_response = status.response["user_content"]
                        print(f"人类回复: {follow_response[:100]}...")  # 只显示前100个字符
                        print("可以继续对话")
                        # 构建新的上下文，包含对第一轮回复的响应
                        follow_up_context = {
                            "message":{
                            "上一轮讨论": follow_response[:100] + "...",  # 简化显示
                            "后续问题": "感谢您的建议！关于您提到的功能，您还有什么补充的吗？"
                            },
                            "question": "请继续讨论。"
                        }
                        
                        # 继续对话
                        continue_result = await provider.async_continue_humanloop(
                            conversation_id=result.conversation_id,
                            context=follow_up_context,
                            metadata={
                                "recipient_email": os.environ.get("TEST_RECIPIENT_EMAIL", "your_email@example.com")
                            }
                        )
                elif status.status == HumanLoopStatus.COMPLETED:
                    follow_response = status.response["user_content"]
                    print(f"人类回复: {follow_response[:100]}...")  # 只显示前100个字符
                    print("对话已结束")
                    break
                elif status.status == HumanLoopStatus.ERROR:
                    print(f"发生错误: {status.error}")
            
            print("等待回复中...")

async def main():
    
    # 加载环境变量
    load_dotenv()

    """主函数"""
    # 从环境变量获取邮箱配置
    smtp_server = os.environ.get("SMTP_SERVER", "smtp.example.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    imap_server = os.environ.get("IMAP_SERVER", "imap.example.com")
    imap_port = int(os.environ.get("IMAP_PORT", "993"))
    
    # 创建 EmailProvider 实例
    provider = EmailProvider(
        name="EmailHumanLoop",
        smtp_server=smtp_server,
        smtp_port=smtp_port,
        imap_server=imap_server,
        imap_port=imap_port,
        check_interval=30,  # 每30秒检查一次邮件
        language="en" # 支持中文模板切换
    )
    
    # 运行示例
    example_type = input("请选择要运行的示例 (1: 审批, 2: 获取信息, 3: 多轮对话): ")
    
    if example_type == "1":
        await approval_example(provider)
    elif example_type == "2":
        await information_example(provider)
    elif example_type == "3":
        await conversation_example(provider)
    else:
        print("无效的选择，请输入1、2或3")

if __name__ == "__main__":
    # 运行主函数
    asyncio.run(main())