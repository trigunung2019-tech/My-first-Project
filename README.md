# My-first-Project — Agentic AI

Agen AI sederhana berbasis **Claude** (Anthropic API). Agen menerima tugas, memutuskan sendiri
tool mana yang dipakai, membaca hasilnya, lalu mengulang sampai tugas selesai.

```
Pengguna ─▶ Agent ─▶ Claude ──(tool_use)──▶ ToolRegistry ─▶ hasil ─┐
                 ▲                                                │
                 └──────────────── tool_result ◀──────────────────┘
                 (berhenti saat Claude memberi jawaban akhir)
```

## Struktur

| File | Isi |
|---|---|
| `agentic_ai/agent.py` | Loop agentik (thinking adaptif, tool use, penanganan refusal/batas langkah) |
| `agentic_ai/tools.py` | Tool bawaan + `ToolRegistry` |
| `agentic_ai/main.py` | CLI interaktif |
| `tests/` | Unit test dengan client tiruan (tanpa panggilan API) |
| `workspace/` | Satu-satunya folder yang boleh dibaca/ditulis agen |

Tool bawaan: `calculate`, `current_time`, `list_files`, `read_file`, `write_file`.

## Cara pakai

1. Pasang dependensi (Python ≥ 3.10):
   ```bash
   python -m venv .venv && source .venv/bin/activate
   pip install -e ".[dev]"
   ```
2. Set API key (dapatkan di https://platform.claude.com/settings/keys):
   ```bash
   export ANTHROPIC_API_KEY=sk-ant-...
   ```
3. Jalankan:
   ```bash
   agentic-ai                                   # mode chat interaktif
   agentic-ai "Hitung 15% dari 2.750.000 lalu simpan ke hasil.txt"
   agentic-ai --effort low "Jam berapa sekarang?"
   ```
4. Tes: `pytest`

## Menambah tool sendiri

```python
from agentic_ai import Agent, Tool, default_registry

reg = default_registry()
reg.register(Tool(
    name="cek_stok",
    description="Cek stok barang berdasarkan kode SKU.",
    input_schema={
        "type": "object",
        "properties": {"sku": {"type": "string"}},
        "required": ["sku"],
        "additionalProperties": False,
    },
    fn=lambda sku: f"Stok {sku}: 12 unit",
))
print(Agent(reg).run("Berapa stok SKU A-100?"))
```

## Catatan

- Model default `claude-opus-5-5` dengan `effort` `high` (ubah via `--model` / `--effort`).
- *Refusal fallback* server-side aktif (`fallbacks="default"`): jika model menolak karena
  klasifikasi keamanan, API otomatis mencoba model cadangan.
- Akses file dikunci di folder `workspace/`; path di luarnya ditolak.
