<div align="center">

![Wordmark Logo of HumanLayer](./docs/images/wordmark.png)
<b face="雅黑">Perfecting AI workflows with human intelligence</b>

</div>

**GoHumanLoop**: A Python library empowering AI agents to dynamically request human input (approval/feedback/conversation) at critical stages. Core features:

- `Human-in-the-loop control`: Lets AI agent systems pause and escalate decisions, enhancing safety and trust.
- `Multi-channel integration`: Supports Terminal, Email, API, and frameworks like LangGraph/CrewAI (soon).
- `Flexible workflows`: Combines automated reasoning with human oversight for reliable AI operations.

Ensures responsible AI deployment by bridging autonomous agents and human judgment.

<div align="center">
<img alt="Repostart" src="https://img.shields.io/github/stars/ptonlix/gohumanloop"/>
<img alt=" Python" src="https://img.shields.io/badge/Python-3.10%2B-blue"/>
<img alt="license" src="https://img.shields.io/badge/license-MIT-green"/>

[简体中文](README-zh.md) | English

</div>

## Table of contents

- [Getting Started](#getting-started)
- [Why GoHumanloop?](#why-humanlayer)
- [Key Features](#key-features)
- [Examples](#examples)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)

## Getting Started

To get started, check out the following example or jump straight into one of the [Examples](./examples/):

- 🦜⛓️ [LangGraph](./examples/langgraph/)

### Example

```shell
pip install gohumanloop
```

```python
import os
from langchain.chat_models import init_chat_model
from typing import Annotated

from langchain_tavily import TavilySearch
from langchain_core.tools import tool
from typing_extensions import TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

# from langgraph.types import Command, interrupt  # 不是用langgraph，而是用gohumanloop

from gohumanloop.adapters.langgraph_adapter import interrupt, create_resume_command

os.environ["DEEPSEEK_API_KEY"] = "sk-xxx"
os.environ["TAVILY_API_KEY"] = "tvly-xxx"

llm = init_chat_model("deepseek:deepseek-chat")

class State(TypedDict):
    messages: Annotated[list, add_messages]

graph_builder = StateGraph(State)

@tool
def human_assistance(query: str) -> str:
    """Request assistance from a human."""
    human_response = interrupt({"query": query})
    return human_response

tool = TavilySearch(max_results=2)
tools = [tool, human_assistance]
llm_with_tools = llm.bind_tools(tools)

def chatbot(state: State):
    message = llm_with_tools.invoke(state["messages"])
    # Because we will be interrupting during tool execution,
    # we disable parallel tool calling to avoid repeating any
    # tool invocations when we resume.
    assert len(message.tool_calls) <= 1
    return {"messages": [message]}

graph_builder.add_node("chatbot", chatbot)

tool_node = ToolNode(tools=tools)
graph_builder.add_node("tools", tool_node)

graph_builder.add_conditional_edges(
    "chatbot",
    tools_condition,
)
graph_builder.add_edge("tools", "chatbot")
graph_builder.add_edge(START, "chatbot")

memory = MemorySaver()

graph = graph_builder.compile(checkpointer=memory)

user_input = "I need some expert guidance for building an AI agent. Could you request assistance for me?"
config = {"configurable": {"thread_id": "1"}}

events = graph.stream(
    {"messages": [{"role": "user", "content": user_input}]},
    config,
    stream_mode="values",
)
for event in events:
    if "messages" in event:
        event["messages"][-1].pretty_print()

# human_response = (
#     "We, the experts are here to help! We'd recommend you check out LangGraph to build your agent."
#     "It's much more reliable and extensible than simple autonomous agents."
# )

# human_command = Command(resume={"data": human_response})

human_command = create_resume_command()

events = graph.stream(human_command, config, stream_mode="values")
for event in events:
    if "messages" in event:
        event["messages"][-1].pretty_print()

```
