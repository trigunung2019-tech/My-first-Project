"""Tim agen: satu koordinator yang membagi tugas ke agen-agen spesialis.

Untuk menyesuaikan dengan perusahaan Anda, ubah daftar SPECIALISTS di bawah:
tambah/hapus spesialis, tulis instruksinya, dan pilih tool yang boleh dipakainya.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import anthropic

from .agent import DEFAULT_MODEL, Agent, AgentError
from .tools import Tool, ToolRegistry


@dataclass
class Specialist:
    name: str
    description: str  # dibaca koordinator untuk memilih spesialis yang tepat
    instructions: str
    tools: list[str] = field(default_factory=list)
    model: str = DEFAULT_MODEL
    effort: str = "medium"


SPECIALISTS = [
    Specialist(
        name="analis_data",
        description="Menghitung angka, menganalisis data dari file (CSV/teks), dan menyusun ringkasan numerik.",
        instructions="Kamu analis data perusahaan. Selalu pakai tool calculate untuk perhitungan "
                     "dan sebutkan sumber angka yang kamu pakai.",
        tools=["calculate", "list_files", "read_file", "current_time"],
    ),
    Specialist(
        name="peneliti_dokumen",
        description="Mencari dan merangkum informasi dari dokumen perusahaan di workspace (SOP, kebijakan, catatan).",
        instructions="Kamu peneliti dokumen perusahaan. Jawab hanya berdasarkan isi file yang kamu baca, "
                     "sebutkan nama file sumbernya, dan katakan terus terang bila informasinya tidak ada.",
        tools=["list_files", "read_file"],
    ),
    Specialist(
        name="penulis",
        description="Menulis atau merapikan dokumen: email, laporan, penawaran, pengumuman. Bisa menyimpan hasil ke file.",
        instructions="Kamu penulis bisnis profesional. Tulis dengan jelas, sopan, dan sesuai tujuan. "
                     "Simpan ke file hanya bila diminta.",
        tools=["read_file", "write_file", "current_time"],
    ),
]

COORDINATOR_PROMPT = """Kamu koordinator tim agen AI perusahaan.
Tugasmu: pahami permintaan pengguna, pecah menjadi sub-tugas, lalu delegasikan setiap sub-tugas
ke spesialis yang paling cocok dengan tool `delegasikan`.

Spesialis yang tersedia:
{roster}

Aturan:
- Spesialis tidak melihat percakapan ini. Tulis setiap tugas lengkap dan mandiri: tujuan,
  data/konteks yang dibutuhkan, dan bentuk hasil yang diharapkan.
- Sub-tugas yang tidak saling bergantung boleh didelegasikan sekaligus (paralel).
- Bila hasil satu spesialis dibutuhkan spesialis lain, tunggu hasilnya lalu teruskan di tugas berikutnya.
- Periksa hasil spesialis; delegasikan ulang bila kurang tepat.
- Pertanyaan sederhana yang tidak butuh spesialis boleh kamu jawab langsung.
- Akhiri dengan jawaban gabungan yang ringkas untuk pengguna, dalam bahasa pengguna."""


def build_team(
    tools: ToolRegistry,
    specialists: list[Specialist] = SPECIALISTS,
    client: Any | None = None,
    model: str = DEFAULT_MODEL,
    effort: str = "high",
    on_event: Callable[[str, Any], None] | None = None,
) -> Agent:
    """Bangun agen koordinator yang punya satu tool: `delegasikan` ke spesialis."""
    client = client or anthropic.Anthropic()
    by_name = {s.name: s for s in specialists}
    # Validasi di awal agar salah ketik nama tool langsung ketahuan.
    toolsets = {s.name: tools.subset(s.tools) for s in specialists}

    def delegasikan(agen: str, tugas: str) -> str:
        spec = by_name.get(agen)
        if spec is None:
            raise ValueError(f"Spesialis '{agen}' tidak ada. Pilihan: {', '.join(by_name)}")
        # Setiap delegasi memakai agen baru agar konteks tiap sub-tugas bersih.
        worker = Agent(
            toolsets[agen], client=client, name=agen, system_prompt=spec.instructions,
            model=spec.model, effort=spec.effort, on_event=on_event,
        )
        if on_event:
            on_event("delegate", {"agent": agen, "task": tugas})
        try:
            return worker.run(tugas)
        except AgentError as exc:
            raise RuntimeError(f"{agen} gagal: {exc}") from exc

    coordinator_tools = ToolRegistry()
    coordinator_tools.register(Tool(
        name="delegasikan",
        description="Serahkan satu sub-tugas ke agen spesialis dan terima hasil kerjanya.",
        input_schema={
            "type": "object",
            "properties": {
                "agen": {"type": "string", "enum": list(by_name), "description": "Nama spesialis."},
                "tugas": {"type": "string", "description": "Instruksi lengkap dan mandiri untuk spesialis."},
            },
            "required": ["agen", "tugas"],
            "additionalProperties": False,
        },
        fn=delegasikan,
    ))

    roster = "\n".join(f"- {s.name}: {s.description}" for s in specialists)
    return Agent(
        coordinator_tools, client=client, name="koordinator",
        system_prompt=COORDINATOR_PROMPT.format(roster=roster),
        model=model, effort=effort, on_event=on_event,
    )
