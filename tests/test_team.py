from types import SimpleNamespace as NS

import pytest

from agentic_ai import Specialist, build_team, default_registry
from test_agent import FakeClient, text, tool_use


def test_coordinator_delegates_to_specialist(tmp_path):
    client = FakeClient([
        # koordinator mendelegasikan
        NS(stop_reason="tool_use", content=[tool_use("d1", "delegasikan",
                                                     {"agen": "analis_data", "tugas": "Hitung 6*7"})]),
        # spesialis memakai kalkulator lalu menjawab
        NS(stop_reason="tool_use", content=[tool_use("c1", "calculate", {"expression": "6*7"})]),
        NS(stop_reason="end_turn", content=[text("42")]),
        # koordinator merangkum
        NS(stop_reason="end_turn", content=[text("Jawabannya 42.")]),
    ])
    events = []
    coordinator = build_team(default_registry(tmp_path), client=client,
                             on_event=lambda kind, data: events.append((kind, data["agent"])))

    assert coordinator.run("Berapa 6 x 7?") == "Jawabannya 42."
    # spesialis hanya diberi tool miliknya
    specialist_tools = {t["name"] for t in client.calls[1]["tools"]}
    assert specialist_tools == {"calculate", "list_files", "read_file", "current_time"}
    assert coordinator.messages[2]["content"][0]["content"] == "42"
    assert ("delegate", "analis_data") in events


def test_unknown_tool_in_specialist_config_fails_fast(tmp_path):
    bad = [Specialist(name="x", description="x", instructions="x", tools=["tidak_ada"])]
    with pytest.raises(KeyError):
        build_team(default_registry(tmp_path), specialists=bad, client=FakeClient([]))
