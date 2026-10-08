"""Tool yang bisa dipanggil agen, plus registry untuk mendaftarkannya."""

from __future__ import annotations

import ast
import datetime as dt
import operator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict[str, Any]
    fn: Callable[..., str]

    def to_api(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
            "strict": True,
        }


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def definitions(self) -> list[dict[str, Any]]:
        return [t.to_api() for t in self._tools.values()]

    def names(self) -> list[str]:
        return list(self._tools)

    def subset(self, names: list[str]) -> "ToolRegistry":
        """Registry baru yang hanya berisi tool dengan nama tertentu."""
        unknown = set(names) - set(self._tools)
        if unknown:
            raise KeyError(f"Tool tidak dikenal: {sorted(unknown)}")
        sub = ToolRegistry()
        for name in names:
            sub.register(self._tools[name])
        return sub

    def run(self, name: str, args: dict[str, Any]) -> tuple[str, bool]:
        """Jalankan tool. Mengembalikan (hasil, is_error)."""
        tool = self._tools.get(name)
        if tool is None:
            return f"Tool '{name}' tidak dikenal.", True
        try:
            return str(tool.fn(**args)), False
        except Exception as exc:  # hasil error dikirim balik ke model
            return f"{type(exc).__name__}: {exc}", True


def _schema(properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


# --- Kalkulator aman (tanpa eval) -------------------------------------------

_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _eval_node(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval_node(node.operand))
    raise ValueError("Ekspresi hanya boleh berisi angka dan + - * / // % **")


def calculate(expression: str) -> str:
    return str(_eval_node(ast.parse(expression, mode="eval")))


def current_time() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


# --- Akses file, dibatasi di dalam folder workspace -------------------------


def _make_file_tools(workspace: Path) -> list[Tool]:
    root = workspace.resolve()
    root.mkdir(parents=True, exist_ok=True)

    def safe(path: str) -> Path:
        target = (root / path).resolve()
        if not target.is_relative_to(root):
            raise PermissionError("Path harus berada di dalam workspace.")
        return target

    def list_files(path: str) -> str:
        target = safe(path)
        entries = sorted(p.relative_to(root).as_posix() + ("/" if p.is_dir() else "")
                         for p in target.iterdir())
        return "\n".join(entries) or "(kosong)"

    def read_file(path: str) -> str:
        return safe(path).read_text(encoding="utf-8")

    def write_file(path: str, content: str) -> str:
        target = safe(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"Tersimpan: {target.relative_to(root).as_posix()} ({len(content)} karakter)"

    return [
        Tool("list_files", "Daftar file dan folder di dalam workspace. Pakai '.' untuk akar workspace.",
             _schema({"path": {"type": "string", "description": "Path relatif terhadap workspace."}}),
             list_files),
        Tool("read_file", "Baca isi file teks di workspace.",
             _schema({"path": {"type": "string", "description": "Path relatif terhadap workspace."}}),
             read_file),
        Tool("write_file", "Tulis (atau timpa) file teks di workspace.",
             _schema({
                 "path": {"type": "string", "description": "Path relatif terhadap workspace."},
                 "content": {"type": "string", "description": "Isi file."},
             }),
             write_file),
    ]


def default_registry(workspace: Path | str = "workspace") -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(Tool(
        "calculate", "Hitung ekspresi aritmetika, mis. '(12.5 * 4) / 3'. Pakai untuk semua perhitungan.",
        _schema({"expression": {"type": "string", "description": "Ekspresi aritmetika."}}),
        calculate,
    ))
    registry.register(Tool(
        "current_time", "Tanggal dan waktu saat ini (ISO 8601, zona waktu lokal).",
        _schema({}), current_time,
    ))
    for tool in _make_file_tools(Path(workspace)):
        registry.register(tool)
    return registry
