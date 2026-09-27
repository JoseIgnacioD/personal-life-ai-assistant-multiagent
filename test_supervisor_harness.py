"""
Standalone test for supervisor_harness.py.

Covers three things, in increasing order of what they prove:
1. Each specialist's tool list has zero overlap with the other two domains.
2. A single-domain question: the supervisor delegates to one specialist,
   which executes a real tool, and the supervisor relays the answer.
3. A cross-domain question: the supervisor delegates to TWO specialists in
   one turn, each executing a different real tool, and combines both
   answers into one final reply — the actual test of orchestration.

Only the model's replies are simulated throughout; every tool call in this
file executes for real against the actual MCP servers.

Run it from the project root, with SERVER_PYTHON and GEMINI_API_KEY set and
the project's .venv active:
    python tests/test_supervisor_harness.py
"""
import asyncio
import sys
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).parent.parent))

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolCall
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain.agents import create_agent
from langchain_mcp_adapters.client import MultiServerMCPClient

import supervisor_harness as sh


class ScriptedFakeModel(BaseChatModel):
    """One shared instance can stand in for every agent, since they all
    really do share one model in production. Responses are consumed in
    actual invocation order, not construction order."""

    responses: List[AIMessage] = []
    _call_count: int = 0

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        response = self.responses[self._call_count]
        self._call_count += 1
        return ChatResult(generations=[ChatGeneration(message=response)])

    @property
    def _llm_type(self) -> str:
        return "scripted-fake"


async def test_specialist_tool_isolation():
    print("== Specialist tool isolation ==")
    client = MultiServerMCPClient(sh.SERVERS)
    all_tools = await client.get_tools()
    assert len(all_tools) == 10

    tasks_names = {t.name for t in all_tools if t.name in sh.TASKS_TOOLS}
    calendar_names = {t.name for t in all_tools if t.name in sh.CALENDAR_TOOLS}
    finance_names = {t.name for t in all_tools if t.name in sh.FINANCE_TOOLS}

    assert not (tasks_names & calendar_names)
    assert not (tasks_names & finance_names)
    assert not (calendar_names & finance_names)
    assert tasks_names | calendar_names | finance_names == {t.name for t in all_tools}
    print("PASS: zero overlap, full coverage\n")


async def test_single_domain_delegation():
    print("== Single-domain delegation ==")
    fake = ScriptedFakeModel(
        responses=[
            AIMessage(content="", tool_calls=[ToolCall(name="tasks", args={"query": "due?"}, id="c1")]),
            AIMessage(content="", tool_calls=[ToolCall(name="list_tasks", args={}, id="c2")]),
            AIMessage(content="You have three tasks."),
            AIMessage(content="You have three tasks due."),
        ]
    )
    sh.get_model = lambda: fake

    supervisor = await sh.build_supervisor()
    answer = await sh.ask(supervisor, "what's due?")

    assert answer == "You have three tasks due."
    assert fake._call_count == 4
    print("PASS: supervisor delegated once, specialist used a real tool\n")


async def test_cross_domain_orchestration():
    print("== Cross-domain orchestration (the real test) ==")
    fake = ScriptedFakeModel(
        responses=[
            AIMessage(content="", tool_calls=[ToolCall(name="tasks", args={"query": "overdue?"}, id="c1")]),
            AIMessage(content="", tool_calls=[ToolCall(name="list_overdue", args={}, id="c2")]),
            AIMessage(content="Two tasks are overdue."),
            AIMessage(content="", tool_calls=[ToolCall(name="finance", args={"query": "afford $30?"}, id="c3")]),
            AIMessage(content="", tool_calls=[ToolCall(name="get_balance", args={}, id="c4")]),
            AIMessage(content="Yes, easily."),
            AIMessage(content="Two tasks are overdue, and yes, you can afford $30."),
        ]
    )
    sh.get_model = lambda: fake

    supervisor = await sh.build_supervisor()
    answer = await sh.ask(supervisor, "What's overdue, and can I afford $30 for dinner?")

    assert "overdue" in answer and "$30" in answer
    assert fake._call_count == 7
    print("PASS: one question, two specialists, two real tools, one combined answer")


async def main():
    await test_specialist_tool_isolation()
    await test_single_domain_delegation()
    await test_cross_domain_orchestration()


if __name__ == "__main__":
    asyncio.run(main())
