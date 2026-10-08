"""CLI interaktif untuk mengobrol dengan agen."""

from __future__ import annotations

import argparse
import json

import anthropic

from .agent import DEFAULT_MODEL, Agent, AgentError
from .team import build_team
from .tools import default_registry


def _print_event(kind: str, data: dict) -> None:
    who = f"[{data['agent']}]"
    if kind == "delegate":
        print(f"  📋 {who} menerima tugas: {data['task'][:120]}")
    elif kind == "tool_call" and data["name"] != "delegasikan":
        print(f"  🔧 {who} {data['name']}({json.dumps(data['input'], ensure_ascii=False)[:120]})")
    elif kind == "tool_result":
        mark = "❌" if data["is_error"] else "✅"
        preview = data["output"].replace("\n", " ")[:120]
        print(f"  {mark} {who} {data['name']}: {preview}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Agen AI berbasis Claude")
    parser.add_argument("prompt", nargs="?", help="Tugas sekali jalan; kosongkan untuk mode interaktif")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--effort", default="high", choices=["low", "medium", "high", "xhigh", "max"])
    parser.add_argument("--workspace", default="workspace", help="Folder yang boleh diakses agen")
    parser.add_argument("--single", action="store_true", help="Pakai satu agen saja, tanpa koordinator")
    args = parser.parse_args()

    tools = default_registry(args.workspace)
    if args.single:
        agent = Agent(tools, model=args.model, effort=args.effort, on_event=_print_event)
    else:
        agent = build_team(tools, model=args.model, effort=args.effort, on_event=_print_event)

    def ask(text: str) -> None:
        try:
            print(f"\n🤖 {agent.run(text)}\n")
        except (AgentError, anthropic.APIError) as exc:
            print(f"\n⚠️  {exc}\n")

    if args.prompt:
        ask(args.prompt)
        return

    print(f"Agentic AI siap ({agent.name}). Ketik 'keluar' untuk berhenti.")
    while True:
        try:
            text = input("Anda> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if text.lower() in {"keluar", "exit", "quit"}:
            break
        if text:
            ask(text)


if __name__ == "__main__":
    main()
