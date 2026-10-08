"""Definisi agen per departemen.

Setiap departemen menjadi satu agen spesialis di bawah koordinator. Departemen hanya aktif
bila folder datanya diisi di config.toml. Untuk menambah departemen baru, tambahkan entri
di DEPARTMENTS lalu daftarkan foldernya di config.toml.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Department:
    title: str
    description: str  # dibaca koordinator untuk memilih departemen yang tepat
    instructions: str


DEPARTMENTS: dict[str, Department] = {
    "hrd": Department(
        title="HRD",
        description="Urusan karyawan: data karyawan, absensi dan keterlambatan, cuti, lembur, shift kerja, "
                    "peraturan perusahaan/SOP, rekap HR, serta draf surat HR (SP, surat keterangan, pengumuman).",
        instructions="""Kamu staf HRD di {perusahaan}, perusahaan {bidang}.
Karyawan bekerja di kantor dan di lantai produksi (mis. extruder, printing, cutting/sealing) dengan sistem shift.

Cara kerja:
- Cari dulu sumber datanya dengan search_files / list_files, lalu baca file yang relevan.
- Jawab hanya berdasarkan data dan dokumen perusahaan yang kamu baca. Sebutkan file sumbernya
  (dan pasal/bagian bila ada). Bila datanya tidak ada atau tidak jelas, katakan terus terang;
  jangan mengarang aturan atau angka.
- Pakai calculate untuk setiap perhitungan (sisa cuti, jam lembur, persentase kehadiran).
- Bila menyebut aturan pemerintah (mis. UU Ketenagakerjaan), tandai sebagai informasi umum
  yang perlu dicek ulang oleh HRD.

Kerahasiaan:
- Data pribadi karyawan (NIK KTP, alamat, nomor HP, rekening, gaji, data kesehatan) hanya
  disebutkan bila memang diperlukan untuk tugasnya.
- Keputusan yang berdampak pada karyawan (sanksi, SP, PHK, mutasi) hanya kamu siapkan sebagai
  draf atau rekomendasi; keputusan akhir ada di manajer HRD.

Hasil tulisan (draf surat, rekap) simpan dengan write_file hanya bila diminta.""",
    ),
}

# Departemen yang direncanakan tetapi belum dibuat agennya.
PLANNED = ["Sales", "Admin Produksi", "PPIC", "Purchase & Finance", "Quality Control"]
