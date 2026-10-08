# Agentic AI Perusahaan

Tim agen AI berbasis **Claude** untuk perusahaan pembuatan kantong plastik. Ada satu agen
**koordinator** dan satu agen untuk tiap **departemen**. Koordinator memahami permintaan,
memecahnya menjadi sub-tugas, lalu menyerahkannya ke agen departemen yang tepat.

```
                          ┌─▶ hrd              ✅ aktif    (folder HRD di server)
Pengguna ─▶ koordinator ──┼─▶ sales            ⏳ menyusul
     ▲                    ├─▶ admin produksi   ⏳ menyusul
     │                    ├─▶ ppic             ⏳ menyusul
     │                    ├─▶ purchase/finance ⏳ menyusul
     │                    └─▶ quality control  ⏳ menyusul
     └──── jawaban gabungan ◀── hasil tiap agen
```

Agen departemen hanya bisa **membaca** folder data departemennya sendiri, dan hanya bisa
**menulis** ke folder hasil yang terpisah. Data asli di server tidak bisa diubah agen.

## Agen HRD

Bisa membaca Excel (`.xlsx`, `.csv`), Word (`.docx`), PDF, dan teks. Contoh permintaan:

- "Siapa saja yang terlambat lebih dari 5 kali bulan September, dan apakah sudah layak SP 1?"
- "Berapa sisa cuti Agus Prasetyo? Bisakah dia cuti 3 hari minggu depan?"
- "Rekap total jam lembur per karyawan bulan September, simpan ke rekap_lembur.md"
- "Buatkan draf SP 1 untuk karyawan yang alpa 3 hari, sesuai peraturan perusahaan"

Folder `contoh_data/HRD/` berisi data **fiktif** untuk mencoba agen sebelum memakai data asli.
Untuk membuatnya ulang: `python scripts/buat_contoh_data.py`.

## Pemasangan di komputer perantara

Server internal tetap offline. Agen dipasang di **satu komputer perantara** yang bisa membaca
shared folder di server, dan hanya boleh ke internet untuk Claude.

```
[Server internal, offline] ──shared folder (read-only)──▶ [Komputer perantara] ──HTTPS──▶ api.anthropic.com
```

1. Di komputer perantara, pasang Python 3.11 atau lebih baru, lalu:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate          # Windows   (Linux: source .venv/bin/activate)
   pip install -e ".[dev]"
   ```
2. Minta tim IT untuk:
   - membagikan folder HRD di server ke komputer ini sebagai **read-only**;
   - membatasi internet komputer ini hanya ke `api.anthropic.com` port 443.
3. Isi `config.toml`: nama perusahaan dan `folder_data` HRD (mis. `'\\SERVER\HRD'` atau `'Z:/HRD'`).
4. Buat API key di https://platform.claude.com/settings/keys, lalu set:
   ```bash
   set ANTHROPIC_API_KEY=sk-ant-...      # Windows   (Linux: export ANTHROPIC_API_KEY=sk-ant-...)
   ```
5. Jalankan:
   ```bash
   agentic-ai                                       # chat dengan koordinator
   agentic-ai "Siapa yang alpa bulan September?"    # satu pertanyaan langsung
   ```
6. Tes (tanpa API key, tanpa internet): `pytest`

## Menambah departemen berikutnya

1. Tambahkan entri di `DEPARTMENTS` pada `agentic_ai/departments.py` (deskripsi dan instruksi kerja).
2. Daftarkan foldernya di `config.toml`:
   ```toml
   [departemen.ppic]
   folder_data = '\\SERVER\PPIC'
   folder_hasil = "hasil/PPIC"
   ```
Koordinator otomatis mengenali departemen baru.

## Struktur

| File | Isi |
|---|---|
| `config.toml` | Nama perusahaan, folder data, dan folder hasil tiap departemen |
| `agentic_ai/departments.py` | Deskripsi dan instruksi kerja tiap agen departemen |
| `agentic_ai/team.py` | Koordinator dan pembentukan tim dari config |
| `agentic_ai/tools.py` | Tool: cari, baca dokumen, baca spreadsheet, tulis hasil, kalkulator |
| `agentic_ai/documents.py` | Pembaca PDF, Word, Excel, CSV |
| `agentic_ai/agent.py` | Loop agen (Claude ↔ tool) |
| `agentic_ai/main.py` | Perintah `agentic-ai` |
| `tests/` | Tes dengan Claude tiruan, tanpa panggilan API |

## Catatan keamanan data

- Isi file yang dibaca agen dikirim ke Claude (Anthropic) untuk diproses. Pastikan ini sesuai
  kebijakan perusahaan, terutama untuk data pribadi karyawan.
- Agen HRD diinstruksikan untuk tidak menampilkan data pribadi (NIK KTP, gaji, rekening, kesehatan)
  kecuali memang diperlukan. Cara paling aman: jangan taruh data yang tidak dibutuhkan di folder HRD
  yang dibagikan ke agen.
- Belum ada login per pengguna: siapa pun yang bisa menjalankan `agentic-ai` di komputer perantara
  bisa bertanya ke semua departemen yang aktif. Batasi siapa yang bisa memakai komputer itu.
- Keputusan seperti SP, sanksi, atau PHK hanya disiapkan sebagai draf/rekomendasi oleh agen.
- Model: `claude-opus-5-5`. Koordinator memakai `effort` `high`, agen departemen `medium`
  (bisa diubah per departemen di `config.toml`).
