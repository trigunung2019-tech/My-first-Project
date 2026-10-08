"""Loop agentik: Claude berpikir, memanggil tool, membaca hasil, lalu lanjut sampai selesai."""

from __future__ import annotations

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
        model: str = DEFAULT_MODEL,
        effort: str = "high",
        max_steps: int = 20,
        on_event: Callable[[str, Any], None] | None = None,
    ) -> None:
        self.tools = tools
        self.client = client or anthropic.Anthropic()
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
                system=SYSTEM_PROMPT,
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

            results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                self.on_event("tool_call", {"name": block.name, "input": block.input})
                output, is_error = self.tools.run(block.name, block.input)
                self.on_event("tool_result", {"name": block.name, "output": output, "is_error": is_error})
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": output,
                    "is_error": is_error,
                })
            # Semua hasil tool dikirim dalam satu pesan user.
            self.messages.append({"role": "user", "content": results})

        raise AgentError(f"Agen berhenti setelah {self.max_steps} langkah tanpa jawaban akhir.")


def _text_of(content: list[Any]) -> str:
    return "\n".join(b.text for b in content if b.type == "text").strip()
