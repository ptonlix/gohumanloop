<div align="center">

![Wordmark Logo of HumanLayer](./docs/images/wordmark.png)
<b face="雅黑">Perfecting AI workflows with human intelligence</b>

</div>

**GoHumanLoop**: A Python library empowering AI agents to dynamically request human input (approval/feedback/conversation) at critical stages. Core features:

- `Human-in-the-loop control`: Lets AI agent systems pause and escalate decisions, enhancing safety and trust.
- `Multi-channel integration`: Supports Terminal, Email, API, and frameworks like LangGraph/CrewAI/...(soon)
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

## 🎹 Getting Started

To get started, check out the following example or jump straight into one of the [Examples Repo](https://github.com/ptonlix/gohumanloop-examples):

- 🦜⛓️ [LangGraph](https://github.com/ptonlix/gohumanloop-examples/tree/main/LangGraph)
- 🚣‍ [CrewAI](https://github.com/ptonlix/gohumanloop-examples/tree/main/CrewAI)

### Installation

**GoHumanLoop** currently supports `Python`.

```shell
pip install gohumanloop
```

### Example

The following example enhances [the official LangGraph example](https://langchain-ai.github.io/langgraph/tutorials/get-started/4-human-in-the-loop/#5-resume-execution) with `human-in-the-loop` functionality.

> 💡 By default, it uses `Terminal` as the `langgraph_adapter` for human interaction.

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

# from langgraph.types import Command, interrupt  # Don't use langgraph, use gohumanloop instead

from gohumanloop.adapters.langgraph_adapter import interrupt, create_resume_command

# Please replace with your Deepseek API Key from https://platform.deepseek.com/usage
os.environ["DEEPSEEK_API_KEY"] = "sk-xxx"
# Please replace with your Tavily API Key from https://app.tavily.com/home
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

# LangGraph code:
# human_response = (
#     "We, the experts are here to help! We'd recommend you check out LangGraph to build your agent."
#     "It's much more reliable and extensible than simple autonomous agents."
# )

# human_command = Command(resume={"data": human_response})

# GoHumanLoop code:
human_command = create_resume_command() # Use this command to resume the execution，instead of using the command above

events = graph.stream(human_command, config, stream_mode="values")
for event in events:
    if "messages" in event:
        event["messages"][-1].pretty_print()

```

- Deployment & Test

Run the above code with the following steps:

```shell
# 1.Initialize environment
uv init gohumanloop-example
cd gohumanloop-example
uv venv .venv --python=3.10

# 2.Copy the above code to main.py

# 3.Deploy and test
uv pip install langchain
uv pip install langchain_tavily
uv pip install langgraph
uv pip install langchain-deepseek
uv pip install gohumanloop

python main.py

```

- Interaction Demo

![终端展示](http://cdn.oyster-iot.cloud/202505232244870.png)

Perform `human-in-the-loop` interaction by entering:

> We, the experts are here to help! We'd recommend you check out LangGraph to build your agent.It's much more reliable and extensible than simple autonomous agents.

![输出结果](http://cdn.oyster-iot.cloud/202505232248390.png)

🚀🚀🚀 Completed successfully ~

➡️ Check out more examples in the [Examples Repository](https://github.com/ptonlix/gohumanloop-examples) and we look foward to your contributions!

## 🎵 Why GoHumanloop?

### Human-in-the-loop

<div align="center">
	<img height=240 src="http://cdn.oyster-iot.cloud/202505210851404.png"><br>
    <b face="雅黑">Even with state-of-the-art agentic reasoning and prompt routing, LLMs are not sufficiently reliable to be given access to high-stakes functions without human oversight</b>
</div>
<br>

`Human-in-the-loop` is an AI system design philosophy that integrates human judgment and supervision into AI decision-making processes. This concept is particularly important in AI Agent systems:

- **Safety Assurance**: Allows human intervention and review at critical decision points to prevent potentially harmful AI decisions
- **Quality Control**: Improves accuracy and reliability of AI outputs through expert feedback
- **Continuous Learning**: AI systems can learn and improve from human feedback, creating a virtuous cycle
- **Clear Accountability**: Maintains ultimate human control over important decisions with clear responsibility

In practice, Human-in-the-loop can take various forms - from simple decision confirmation to deep human-AI collaborative dialogues - ensuring optimal balance between autonomy and human oversight to maximize the potential of AI Agent systems.

#### Typical Use Cases

<div align="center">
	<img height=120 src="http://cdn.oyster-iot.cloud/tool-call-review.png"><br>
    <b face="雅黑"> A human can review and edit the output from the agent before proceeding. This is particularly critical in applications where the tool calls requested may be sensitive or require human oversight.</b>
</div>
<br>

- 🛠️ Tool Call Review: Humans can review, edit or approve tool call requests initiated by LLMs before execution
- ✅ Model Output Verification: Humans can review, edit or approve content generated by LLMs (text, decisions, etc.)
- 💡 Context Provision: Allows LLMs to actively request human input for clarification, additional details or multi-turn conversation context

### Secure and Efficient Go➡Humanloop

`GoHumanloop` provides a set of tools deeply integrated within AI Agents to ensure constant `Human-in-the-loop` oversight. It deterministically ensures high-risk function calls must undergo human review while also enabling human expert feedback, thereby improving AI system reliability and safety while reducing risks from LLM hallucinations.

<div align="center">
	<img height=420 src="http://cdn.oyster-iot.cloud/202505210943862.png"><br>
    <b face="雅黑"> The Outer-Loop and Inversion of Control</b>
</div>
<br>

Through `GoHumanloop`'s encapsulation, you can implement secure and efficient `Human-in-the-loop` when requesting tools, Agent nodes, MCP services and other Agents.

## 📚 Key Features

<div align="center">
	<img height=360 src="http://cdn.oyster-iot.cloud/202505291027894.png"><br>
    <b face="雅黑"> GoHumanLoop Architecture</b>
</div>
<br>

`GoHumanloop` offers the following core capabilities:

- **Approval:** Requests human review or approval when executing specific tool calls or Agent nodes
- **Information:** Obtains critical human input during task execution to reduce LLM hallucination risks
- **Conversation:** Enables multi-turn interactions with humans through dialogue to acquire richer contextual information
- **Framework-specific Integration:** Provides specialized integration methods for specific Agent frameworks, such as `interrupt` and `resume` for `LangGraph`

## 📅 Roadmap

| Feature           | Status     |
| ----------------- | ---------- |
| Approval          | ⚙️ Beta    |
| Information       | ⚙️ Beta    |
| Conversation      | ⚙️ Beta    |
| Email Provider    | ⚙️ Beta    |
| Terminal Provider | ⚙️ Beta    |
| API Provider      | ⚙️ Beta    |
| Default Manager   | ⚙️ Beta    |
| GLH Manager       | 🗓️ Planned |
| Langchain Support | ⚙️ Beta    |
| CrewAI Support    | 🗓️ Planned |

- 💡 GLH Manager - GoHumanLoop Manager will integrate with the upcoming GoHumanLoop Hub platform to provide users with more flexible management options.

## 🤝 Contributing

The GoHumanLoop SDK and documentation are open source. We welcome contributions in the form of issues, documentation and PRs. For more details, please see [CONTRIBUTING.md](./CONTRIBUTING.md)

## 📱 Contact

<img height=300 src="http://cdn.oyster-iot.cloud/202505231802103.png"/>

🎉 If you're interested in this project, feel free to scan the QR code to contact the author.

## 🌟 Star History

[![Star History Chart](https://api.star-history.com/svg?repos=gohumanloop/gohumanloop&type=Date)](https://www.star-history.com/#gohumanloop/gohumanloop&Date)
