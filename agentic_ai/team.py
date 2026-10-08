"""Tim agen: satu koordinator yang membagi tugas ke agen spesialis (satu per departemen)."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import anthropic

from .agent import DEFAULT_MODEL, Agent, AgentError
from .departments import DEPARTMENTS, PLANNED
from .tools import Tool, ToolRegistry, base_registry, folder_tools


@dataclass
class Specialist:
    name: str
    description: str  # dibaca koordinator untuk memilih spesialis yang tepat
    instructions: str
    tools: ToolRegistry
    model: str = DEFAULT_MODEL
    effort: str = "medium"


COORDINATOR_PROMPT = """Kamu koordinator tim agen AI di {perusahaan}, perusahaan {bidang}.
Tugasmu: pahami permintaan pengguna, pecah menjadi sub-tugas, lalu delegasikan setiap sub-tugas
ke agen departemen yang tepat dengan tool `delegasikan`.

Agen departemen yang aktif:
{roster}

Departemen yang belum punya agen: {planned}.
Bila permintaan menyangkut departemen itu, katakan bahwa agennya belum tersedia.

Aturan:
- Agen departemen tidak melihat percakapan ini. Tulis setiap tugas lengkap dan mandiri: tujuan,
  data/konteks yang dibutuhkan, dan bentuk hasil yang diharapkan.
- Sub-tugas yang tidak saling bergantung boleh didelegasikan sekaligus (paralel).
- Bila hasil satu agen dibutuhkan agen lain, tunggu hasilnya lalu teruskan di tugas berikutnya.
- Periksa hasil agen; delegasikan ulang bila kurang tepat atau tidak menyebut sumber data.
- Jangan mengarang data perusahaan sendiri. Pertanyaan umum yang tidak butuh data boleh kamu jawab langsung.
- Akhiri dengan jawaban gabungan yang ringkas untuk pengguna, dalam bahasa pengguna."""


def build_team(
    specialists: list[Specialist],
    company: dict[str, str],
    client: Any | None = None,
    model: str = DEFAULT_MODEL,
    effort: str = "high",
    on_event: Callable[[str, Any], None] | None = None,
) -> Agent:
    """Bangun agen koordinator yang punya satu tool: `delegasikan` ke spesialis."""
    if not specialists:
        raise ValueError("Belum ada agen departemen yang aktif. Isi folder datanya di config.toml.")
    client = client or anthropic.Anthropic()
    by_name = {s.name: s for s in specialists}

    def delegasikan(agen: str, tugas: str) -> str:
        spec = by_name.get(agen)
        if spec is None:
            raise ValueError(f"Agen '{agen}' tidak ada. Pilihan: {', '.join(by_name)}")
        # Setiap delegasi memakai agen baru agar konteks tiap sub-tugas bersih.
        worker = Agent(
            spec.tools, client=client, name=agen, system_prompt=spec.instructions,
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
        description="Serahkan satu sub-tugas ke agen departemen dan terima hasil kerjanya.",
        input_schema={
            "type": "object",
            "properties": {
                "agen": {"type": "string", "enum": list(by_name), "description": "Nama agen departemen."},
                "tugas": {"type": "string", "description": "Instruksi lengkap dan mandiri untuk agen."},
            },
            "required": ["agen", "tugas"],
            "additionalProperties": False,
        },
        fn=delegasikan,
    ))

    active = {s.name for s in specialists}
    planned = [p for p in PLANNED if p.lower() not in active] or ["-"]
    prompt = COORDINATOR_PROMPT.format(
        **company,
        roster="\n".join(f"- {s.name}: {s.description}" for s in specialists),
        planned=", ".join(planned),
    )
    return Agent(coordinator_tools, client=client, name="koordinator", system_prompt=prompt,
                 model=model, effort=effort, on_event=on_event)


def load_config(path: Path | str) -> dict[str, Any]:
    path = Path(path)
    with path.open("rb") as f:
        config = tomllib.load(f)
    config["_dir"] = path.resolve().parent
    return config


def company_info(config: dict[str, Any]) -> dict[str, str]:
    info = config.get("perusahaan", {})
    return {"perusahaan": info.get("nama", "perusahaan"), "bidang": info.get("bidang", "")}


def specialists_from_config(config: dict[str, Any]) -> list[Specialist]:
    """Satu spesialis untuk setiap departemen yang terdaftar di config.toml."""
    base_dir: Path = config.get("_dir", Path.cwd())
    company = company_info(config)
    specialists = []
    for key, settings in config.get("departemen", {}).items():
        dept = DEPARTMENTS.get(key)
        if dept is None:
            raise KeyError(f"Departemen '{key}' di config.toml belum didefinisikan di departments.py. "
                           f"Tersedia: {', '.join(DEPARTMENTS)}")
        tools = base_registry()
        output_dir = settings.get("folder_hasil")
        for tool in folder_tools(base_dir / settings["folder_data"],
                                 base_dir / output_dir if output_dir else None):
            tools.register(tool)
        specialists.append(Specialist(
            name=key,
            description=dept.description,
            instructions=dept.instructions.format(**company),
            tools=tools,
            model=settings.get("model", DEFAULT_MODEL),
            effort=settings.get("effort", "medium"),
        ))
    return specialists
