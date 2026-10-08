"""Tool yang bisa dipanggil agen, plus registry untuk mendaftarkannya."""

from __future__ import annotations

import ast
import datetime as dt
import operator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from . import documents


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


# --- Akses folder data, dibatasi di dalam satu folder akar ------------------

CHUNK_CHARS = 30_000


def _resolver(root: Path) -> Callable[[str], Path]:
    def safe(path: str) -> Path:
        target = (root / path).resolve()
        if not target.is_relative_to(root):
            raise PermissionError("Path harus berada di dalam folder yang diizinkan.")
        if not target.exists():
            raise FileNotFoundError(f"'{path}' tidak ditemukan.")
        return target

    return safe


def folder_tools(data_dir: Path | str, output_dir: Path | str | None = None) -> list[Tool]:
    """Tool baca-saja untuk data_dir, plus write_file ke output_dir bila diberikan."""
    root = Path(data_dir).resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Folder data tidak ditemukan: {root}")
    safe = _resolver(root)
    text_cache: dict[Path, tuple[float, str]] = {}

    def cached_text(path: Path) -> str:
        mtime = path.stat().st_mtime
        hit = text_cache.get(path)
        if hit is None or hit[0] != mtime:
            hit = (mtime, documents.document_text(path))
            text_cache[path] = hit
        return hit[1]

    def rel(path: Path) -> str:
        return path.relative_to(root).as_posix()

    def list_files(path: str) -> str:
        target = safe(path)
        entries = sorted(rel(p) + ("/" if p.is_dir() else "") for p in target.iterdir()
                         if not p.name.startswith(("~$", ".")))
        return "\n".join(entries) or "(kosong)"

    def read_document(path: str, start_char: int) -> str:
        text = cached_text(safe(path))
        chunk = text[start_char:start_char + CHUNK_CHARS]
        end = start_char + len(chunk)
        if end < len(text):
            chunk += f"\n\n[Bersambung: {len(text) - end} karakter lagi. Panggil lagi dengan start_char={end}.]"
        return chunk or "(dokumen kosong atau tidak berisi teks yang bisa dibaca)"

    def read_spreadsheet(path: str, sheet: str, contains: str, start_row: int, max_rows: int) -> str:
        all_sheets = documents.sheets(safe(path))
        name = sheet or next(iter(all_sheets), "")
        if name not in all_sheets:
            raise KeyError(f"Sheet '{sheet}' tidak ada. Sheet tersedia: {', '.join(all_sheets)}")
        rows = all_sheets[name]
        header, body = (rows[0], rows[1:]) if rows else ([], [])
        if contains:
            body = [r for r in body if any(contains.lower() in c.lower() for c in r)]
        page = body[start_row:start_row + max(1, min(max_rows, 500))]
        lines = [f"Sheet: {name} (sheet lain: {', '.join(n for n in all_sheets if n != name) or '-'})",
                 f"Baris cocok: {len(body)}, ditampilkan {start_row}-{start_row + len(page) - 1}",
                 " | ".join(header), *(" | ".join(r) for r in page)]
        return "\n".join(lines)

    def search_files(keyword: str) -> str:
        needle = keyword.lower()
        hits: list[str] = []
        for path in sorted(root.rglob("*")):
            if len(hits) >= 30:
                hits.append("[Hasil dibatasi 30. Persempit kata kunci.]")
                break
            if path.suffix.lower() not in documents.SUPPORTED_SUFFIXES or path.name.startswith("~$"):
                continue
            if needle in path.name.lower():
                hits.append(f"{rel(path)}: (nama file cocok)")
            try:
                text = cached_text(path)
            except Exception:
                continue
            for line in text.splitlines():
                if needle in line.lower():
                    hits.append(f"{rel(path)}: {line.strip()[:200]}")
                    break
        return "\n".join(hits) or f"Tidak ada file yang memuat '{keyword}'."

    path_prop = {"type": "string", "description": "Path relatif terhadap folder data."}
    tools = [
        Tool("list_files", "Daftar file dan subfolder. Pakai '.' untuk folder utama.",
             _schema({"path": path_prop}), list_files),
        Tool("search_files", "Cari kata kunci di nama dan isi semua dokumen (PDF, Word, Excel, CSV, teks). "
                             "Mulai dari sini bila belum tahu file mana yang relevan.",
             _schema({"keyword": {"type": "string", "description": "Kata atau frasa yang dicari."}}),
             search_files),
        Tool("read_document", "Baca isi dokumen PDF, Word (.docx), atau teks per potongan "
                              f"{CHUNK_CHARS} karakter.",
             _schema({"path": path_prop,
                      "start_char": {"type": "integer", "description": "Mulai dari karakter ke berapa; 0 untuk awal."}}),
             read_document),
        Tool("read_spreadsheet", "Baca baris dari file Excel (.xlsx) atau CSV, bisa disaring kata kunci.",
             _schema({
                 "path": path_prop,
                 "sheet": {"type": "string", "description": "Nama sheet; string kosong untuk sheet pertama."},
                 "contains": {"type": "string", "description": "Hanya baris yang memuat teks ini; kosong untuk semua."},
                 "start_row": {"type": "integer", "description": "Indeks baris data pertama (0 = setelah header)."},
                 "max_rows": {"type": "integer", "description": "Jumlah baris maksimum (≤ 500)."},
             }),
             read_spreadsheet),
    ]

    if output_dir is not None:
        out = Path(output_dir).resolve()
        out.mkdir(parents=True, exist_ok=True)

        def write_file(path: str, content: str) -> str:
            target = (out / path).resolve()
            if not target.is_relative_to(out):
                raise PermissionError("Path harus berada di dalam folder hasil.")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            return f"Tersimpan di folder hasil: {target.relative_to(out).as_posix()} ({len(content)} karakter)"

        tools.append(Tool(
            "write_file", "Simpan teks (mis. draf surat, laporan, rekap) ke folder hasil. Data asli tidak bisa diubah.",
            _schema({"path": {"type": "string", "description": "Nama file di folder hasil."},
                     "content": {"type": "string", "description": "Isi file."}}),
            write_file,
        ))
    return tools


def base_registry() -> ToolRegistry:
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
    return registry


def default_registry(workspace: Path | str = "workspace") -> ToolRegistry:
    """Registry untuk mode satu agen: workspace bisa dibaca dan ditulis."""
    Path(workspace).mkdir(parents=True, exist_ok=True)
    registry = base_registry()
    for tool in folder_tools(workspace, output_dir=workspace):
        registry.register(tool)
    return registry
