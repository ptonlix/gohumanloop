import asyncio
from crewai import Agent, Task, Crew, Process
from crewai.tasks.task import TaskOutput
import gohumanloop as ghl

# 创建人机交互适配器
adapter = ghl.create_crewai_adapter(
    provider=ghl.create_api_provider(api_key="your_api_key")
)

# 定义代理
researcher = Agent(
    name="研究员",
    goal="研究并提供准确的信息",
    backstory="你是一名专业研究员，擅长收集和分析信息。",
    verbose=True
)

writer = Agent(
    name="作家",
    goal="创作引人入胜的内容",
    backstory="你是一名有才华的作家，擅长将复杂信息转化为引人入胜的内容。",
    verbose=True
)

# 定义需要人类批准的任务执行方法
@adapter.requires_approval(
    context_builder=lambda agent, args: {
        "title": "发布内容审核",
        "description": "Agent 请求发布以下内容",
        "agent": agent.name,
        "task": args[0].description,
        "content": args[0].context.get("content", "无内容")
    },
    blocking=True
)
async def publish_content(agent, task):
    """发布内容（需要人类批准）"""
    content = task.context.get("content", "")
    # 这里是发布内容的实际逻辑
    return TaskOutput(
        output=f"内容已发布: {content[:100]}...",
        result={"published": True, "timestamp": "2023-06-01"}
    )

# 定义任务
research_task = Task(
    description="研究人工智能的最新发展",
    agent=researcher,
    expected_output="一份关于AI最新发展的研究报告"
)

writing_task = Task(
    description="根据研究报告撰写一篇博客文章",
    agent=writer,
    expected_output="一篇关于AI最新发展的博客文章",
    context={"previous_task_output": ""}
)

publishing_task = Task(
    description="发布博客文章",
    agent=writer,
    expected_output="发布确认",
    context={"content": ""},
    async_execution=publish_content  # 使用自定义的需要人类批准的执行方法
)

# 创建工作流
crew = Crew(
    agents=[researcher, writer],
    tasks=[research_task, writing_task, publishing_task],
    process=Process.sequential
)

# 运行工作流
async def run_crew():
    result = await crew.kickoff()
    return result

if __name__ == "__main__":
    asyncio.run(run_crew())