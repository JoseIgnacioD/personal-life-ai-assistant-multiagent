"""
supervisor_harness.py — multi-agent orchestration.

Milestone A (this version): three specialist agents, each seeing only its
own domain's tools, instead of one flat agent holding all ten.

Deliberately self-contained: does not import from harness.py or
mcp_client.py, even though it lives alongside them for now. This file is
meant to be able to move into its own project later without carrying a
hidden dependency on the other one — a few duplicated lines now is cheaper
than a broken import later.

Run it with:
    python supervisor_harness.py
"""
import asyncio
import os

from langchain.agents import create_agent
from langchain.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_mcp_adapters.client import MultiServerMCPClient

SERVER_PYTHON = os.environ["SERVER_PYTHON"]

SERVERS = {
    "tasks": {
        "command": SERVER_PYTHON,
        "args": ["tasks_mcp.py"],
        "transport": "stdio",
    },
    "calendar": {
        "command": SERVER_PYTHON,
        "args": ["calendar_mcp.py"],
        "transport": "stdio",
    },
    "finance": {
        "command": SERVER_PYTHON,
        "args": ["finance_mcp.py"],
        "transport": "stdio",
    },
}

TASKS_TOOLS = {"list_tasks", "add_task", "complete_task", "list_overdue"}
CALENDAR_TOOLS = {"list_events", "add_event", "find_free_slots"}
FINANCE_TOOLS = {"add_transaction", "get_balance", "monthly_summary"}


def get_model() -> ChatGoogleGenerativeAI:
    """Google's native SDK handles Gemini's thought_signature round-trip
    automatically — unlike ChatOpenAI pointed at the OpenAI-compatible
    endpoint, which has no field for it."""
    return ChatGoogleGenerativeAI(
        model="gemini-3.1-flash-lite",
        google_api_key=os.environ["GEMINI_API_KEY"],
    )


def extract_text(content) -> str:
    """AIMessage.content is usually a plain string, but Gemini's models
    return a list of content blocks instead when a thought signature is
    attached — e.g. [{'type': 'text', 'text': '...', 'extras': {...}}].
    Pull out just the actual text, discarding the signature.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts)
    return str(content)


async def build_specialists():
    """Connect once, then split the ten tools into three restricted groups —
    one create_agent() per domain, each only able to see its own tools."""
    client = MultiServerMCPClient(SERVERS)
    all_tools = await client.get_tools()

    model = get_model()

    tasks_agent = create_agent(model, [t for t in all_tools if t.name in TASKS_TOOLS])
    calendar_agent = create_agent(model, [t for t in all_tools if t.name in CALENDAR_TOOLS])
    finance_agent = create_agent(model, [t for t in all_tools if t.name in FINANCE_TOOLS])

    return tasks_agent, calendar_agent, finance_agent


async def ask(agent, question: str) -> str:
    response = await agent.ainvoke({"messages": [{"role": "user", "content": question}]})
    return extract_text(response["messages"][-1].content)


async def build_supervisor():
    """The supervisor has no database tools of its own — only the ability
    to delegate to one of the three specialists, each wrapped as a tool
    following LangChain's own documented subagents-as-tools pattern."""
    tasks_agent, calendar_agent, finance_agent = await build_specialists()
    model = get_model()

    @tool("tasks", description="Handle anything about tasks: listing, adding, completing, or checking what's overdue.")
    async def call_tasks_agent(query: str) -> str:
        return await ask(tasks_agent, query)

    @tool("calendar", description="Handle anything about the calendar: listing events, adding events, or finding free time slots.")
    async def call_calendar_agent(query: str) -> str:
        return await ask(calendar_agent, query)

    @tool("finance", description="Handle anything about money: balance, recording transactions, or spending summaries.")
    async def call_finance_agent(query: str) -> str:
        return await ask(finance_agent, query)

    return create_agent(model, [call_tasks_agent, call_calendar_agent, call_finance_agent])


async def main() -> None:
    supervisor = await build_supervisor()

    print("-- supervisor, single-domain question --")
    print(await ask(supervisor, "What tasks do I have due this week?"))

    print("\n-- supervisor, a question spanning two domains --")
    print(await ask(supervisor, "What tasks are overdue, and can I afford $30 for dinner tonight?"))


if __name__ == "__main__":
    asyncio.run(main())
