import asyncio
import gohumanloop as ghl

async def main():
    # 创建API提供者
    provider = ghl.create_api_provider(
        api_url="https://api.gohumanloop.com",
        api_key="your_api_key"
    )
    
    # 创建管理器
    manager = ghl.create_manager(provider)
    
    # 请求批准
    result = await manager.request_approval(
        task_id="example_task",
        context={
            "title": "示例批准请求",
            "description": "这是一个示例批准请求",
            "action": "执行敏感操作",
            "reason": "需要人类确认这个操作是安全的"
        },
        blocking=True,  # 阻塞等待结果
        timeout=60  # 60秒超时
    )
    
    # 检查结果
    if result.status == ghl.ApprovalStatus.APPROVED:
        print("请求被批准！")
        print(f"反馈: {result.feedback}")
    elif result.status == ghl.ApprovalStatus.REJECTED:
        print("请求被拒绝。")
        print(f"反馈: {result.feedback}")
    else:
        print(f"请求状态: {result.status.value}")
        if result.error:
            print(f"错误: {result.error}")

if __name__ == "__main__":
    asyncio.run(main())