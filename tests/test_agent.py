from types import SimpleNamespace as NS

import pytest

from agentic_ai import Agent, default_registry
from agentic_ai.agent import AgentError


class FakeClient:
    """Meniru client.beta.messages.create dengan respons yang sudah disiapkan."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.beta = NS(messages=NS(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


def text(t):
    return NS(type="text", text=t)


def tool_use(id_, name, input_):
    return NS(type="tool_use", id=id_, name=name, input=input_)


def test_agent_calls_tool_then_answers(tmp_path):
    client = FakeClient([
        NS(stop_reason="tool_use", content=[tool_use("t1", "calculate", {"expression": "6 * 7"})]),
        NS(stop_reason="end_turn", content=[text("Hasilnya 42.")]),
    ])
    agent = Agent(default_registry(tmp_path), client=client)

    assert agent.run("Berapa 6 x 7?") == "Hasilnya 42."
    tool_result = agent.messages[2]["content"][0]  # user -> assistant -> tool_result
    assert tool_result == {"type": "tool_result", "tool_use_id": "t1", "content": "42", "is_error": False}


def test_agent_raises_on_refusal(tmp_path):
    client = FakeClient([NS(stop_reason="refusal", content=[])])
    with pytest.raises(AgentError):
        Agent(default_registry(tmp_path), client=client).run("x")


def test_agent_stops_after_max_steps(tmp_path):
    loop = NS(stop_reason="tool_use", content=[tool_use("t", "current_time", {})])
    client = FakeClient([loop] * 3)
    with pytest.raises(AgentError):
        Agent(default_registry(tmp_path), client=client, max_steps=3).run("x")


def test_file_tools_stay_inside_workspace(tmp_path):
    reg = default_registry(tmp_path)
    assert reg.run("write_file", {"path": "a/b.txt", "content": "halo"}) == ("Tersimpan: a/b.txt (4 karakter)", False)
    assert reg.run("read_file", {"path": "a/b.txt"}) == ("halo", False)
    _, is_error = reg.run("read_file", {"path": "../../etc/passwd"})
    assert is_error


def test_calculator_rejects_code(tmp_path):
    reg = default_registry(tmp_path)
    assert reg.run("calculate", {"expression": "2 ** 10"}) == ("1024", False)
    _, is_error = reg.run("calculate", {"expression": "__import__('os')"})
    assert is_error
