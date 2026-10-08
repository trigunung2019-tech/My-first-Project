# My-first-Project — Agentic AI

Sistem multi-agen berbasis **Claude** (Anthropic API) untuk perusahaan. Agen **koordinator**
menerima permintaan, memecahnya menjadi sub-tugas, lalu mendelegasikannya ke agen **spesialis**.
Sub-tugas yang tidak saling bergantung dikerjakan paralel.

```
                         ┌─▶ analis_data       (calculate, read_file, ...)
Pengguna ─▶ koordinator ─┼─▶ peneliti_dokumen  (list_files, read_file)
     ▲                   └─▶ penulis           (read_file, write_file)
     └──── jawaban gabungan ◀── hasil tiap spesialis
```

Setiap spesialis hanya mendapat tool yang diizinkan untuknya, dan memulai dengan konteks
bersih untuk tiap tugas.

## Struktur

| File | Isi |
|---|---|
| `agentic_ai/team.py` | **Koordinator + daftar spesialis** (edit di sini untuk perusahaan Anda) |
| `agentic_ai/agent.py` | Loop agentik (thinking adaptif, tool use paralel, penanganan refusal/batas langkah) |
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
   agentic-ai                                   # chat dengan koordinator
   agentic-ai "Hitung total penjualan di penjualan.csv lalu tulis email laporannya ke manajer"
   agentic-ai --single "Jam berapa sekarang?"   # satu agen saja, tanpa koordinator
   ```
4. Tes: `pytest`

## Menambah agen spesialis

Tambahkan entri ke `SPECIALISTS` di `agentic_ai/team.py`. Koordinator otomatis mengenalinya:

```python
Specialist(
    name="admin_gudang",
    description="Mengecek stok dan membuat permintaan restock.",  # dibaca koordinator
    instructions="Kamu admin gudang. Laporkan stok apa adanya.",
    tools=["cek_stok", "write_file"],   # nama tool yang terdaftar di registry
    effort="low",                       # low/medium untuk tugas rutin, lebih hemat
),
```

## Menambah tool sendiri

```python
from agentic_ai import Agent, Tool, build_team, default_registry

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
print(Agent(reg).run("Berapa stok SKU A-100?"))      # satu agen
# atau: build_team(reg, specialists=[...]).run(...)  # tim dengan koordinator
```

## Catatan

- Model default `claude-opus-5-5`. Koordinator memakai `effort` `high` (ubah via `--effort`),
  spesialis `medium` (ubah per spesialis di `team.py`, termasuk `model` bila ingin lebih hemat).
- *Refusal fallback* server-side aktif (`fallbacks="default"`): jika model menolak karena
  klasifikasi keamanan, API otomatis mencoba model cadangan.
- Akses file dikunci di folder `workspace/`; path di luarnya ditolak.
