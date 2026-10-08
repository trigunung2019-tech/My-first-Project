"""Loop agentik: Claude berpikir, memanggil tool, membaca hasil, lalu lanjut sampai selesai."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

import anthropic

from .tools import ToolRegistry

DEFAULT_MODEL = "claude-opus-5-5"

SYSTEM_PROMPT = """Kamu adalah asisten agentik yang menyelesaikan tugas secara mandiri.
Pecah tugas menjadi langkah, pakai tool yang tersedia bila membantu, periksa hasilnya,
dan berikan jawaban akhir yang ringkas. Jawab dalam bahasa yang dipakai pengguna."""


class AgentError(RuntimeError):
    pass


class Agent:
    def __init__(
        self,
        tools: ToolRegistry,
        client: Any | None = None,
        system_prompt: str = SYSTEM_PROMPT,
        name: str = "agen",
        model: str = DEFAULT_MODEL,
        effort: str = "high",
        max_steps: int = 20,
        on_event: Callable[[str, Any], None] | None = None,
    ) -> None:
        self.tools = tools
        self.client = client or anthropic.Anthropic()
        self.system_prompt = system_prompt
        self.name = name
        self.model = model
        self.effort = effort
        self.max_steps = max_steps
        self.on_event = on_event or (lambda kind, data: None)
        # Riwayat bersifat append-only agar thinking block tetap valid antar giliran.
        self.messages: list[dict[str, Any]] = []

    def run(self, user_input: str) -> str:
        self.messages.append({"role": "user", "content": user_input})

        for _ in range(self.max_steps):
            response = self.client.beta.messages.create(
                model=self.model,
                max_tokens=16000,
                system=self.system_prompt,
                tools=self.tools.definitions(),
                thinking={"type": "adaptive"},
                output_config={"effort": self.effort},
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
                messages=self.messages,
            )
            # Simpan seluruh content (termasuk thinking & tool_use), bukan hanya teksnya.
            self.messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "refusal":
                raise AgentError("Permintaan ditolak oleh model.")
            if response.stop_reason == "max_tokens":
                raise AgentError("Respons terpotong (max_tokens).")
            if response.stop_reason == "pause_turn":
                continue
            if response.stop_reason != "tool_use":
                return _text_of(response.content)

            calls = [b for b in response.content if b.type == "tool_use"]
            # Panggilan tool dalam satu giliran dijalankan paralel (mis. delegasi ke beberapa agen).
            with ThreadPoolExecutor() as pool:
                outputs = list(pool.map(self._run_tool, calls))
            results = [
                {"type": "tool_result", "tool_use_id": call.id, "content": output, "is_error": is_error}
                for call, (output, is_error) in zip(calls, outputs)
            ]
            # Semua hasil tool dikirim dalam satu pesan user.
            self.messages.append({"role": "user", "content": results})

        raise AgentError(f"{self.name} berhenti setelah {self.max_steps} langkah tanpa jawaban akhir.")

    def _run_tool(self, call: Any) -> tuple[str, bool]:
        self.on_event("tool_call", {"agent": self.name, "name": call.name, "input": call.input})
        output, is_error = self.tools.run(call.name, call.input)
        self.on_event("tool_result", {"agent": self.name, "name": call.name, "output": output, "is_error": is_error})
        return output, is_error


def _text_of(content: list[Any]) -> str:
    return "\n".join(b.text for b in content if b.type == "text").strip()
