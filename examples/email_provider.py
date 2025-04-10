import asyncio
import gohumanloop as ghl
from gohumanloop.providers.email_provider import EmailProvider

async def main():
    # 创建邮件提供者
    provider = EmailProvider(
        smtp_server="smtp.gmail.com",
        smtp_port=587,
        imap_server="imap.gmail.com",
        imap_port=993,
        username="your_email@gmail.com",
        password="your_app_password",  # 使用应用专用密码
        recipients=["approver@example.com"],
        check_interval=30.0  # 每30秒检查一次邮件
    )
    
    # 创建管理器
    manager = ghl.create_manager(provider)
    
    # 请求批准
    result = await manager.request_approval(
        task_id="email_example",
        context={
            "title": "邮件批准示例",
            "description": "这是一个通过邮件请求批准的示例",
            "action": "执行数据迁移",
            "reason": "需要将数据从测试环境迁移到生产环境"
        },
        blocking=True,  # 阻塞等待结果
        timeout=300  # 5分钟超时
    )
    
    # 检查结果
    if result.status == ghl.ApprovalStatus.APPROVED:
        print("请求被批准！")
        print(f"批准者: {result.approved_by}")
        print(f"批准时间: {result.approved_at}")
        print(f"反馈: {result.feedback}")
    elif result.status == ghl.ApprovalStatus.REJECTED:
        print("请求被拒绝。")
        print(f"反馈: {result.feedback}")
    else:
        print(f"请求状态: {result.status.value}")
        if result.error:
            print(f"错误: {result.error}")
    
    # 停止邮件轮询
    await provider.stop_polling()

if __name__ == "__main__":
    asyncio.run(main())