from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from agentic_ai import build_team, folder_tools, base_registry, load_config, specialists_from_config
from test_agent import FakeClient, text, tool_use

ROOT = Path(__file__).resolve().parent.parent
COMPANY = {"perusahaan": "PT Uji", "bidang": "pembuatan kantong plastik"}


@pytest.fixture
def config(tmp_path):
    data = tmp_path / "HRD"
    data.mkdir()
    (data / "aturan.txt").write_text("Pasal 9: cuti tahunan 12 hari kerja.", encoding="utf-8")
    cfg = tmp_path / "config.toml"
    cfg.write_text('[perusahaan]\nnama = "PT Uji"\nbidang = "pembuatan kantong plastik"\n'
                   '[departemen.hrd]\nfolder_data = "HRD"\nfolder_hasil = "hasil"\n', encoding="utf-8")
    return load_config(cfg)


def test_coordinator_delegates_to_hrd(config):
    client = FakeClient([
        NS(stop_reason="tool_use", content=[tool_use("d1", "delegasikan",
                                                     {"agen": "hrd", "tugas": "Berapa hak cuti tahunan?"})]),
        NS(stop_reason="tool_use", content=[tool_use("s1", "search_files", {"keyword": "cuti"})]),
        NS(stop_reason="end_turn", content=[text("12 hari (aturan.txt, Pasal 9)")]),
        NS(stop_reason="end_turn", content=[text("Hak cuti tahunan 12 hari.")]),
    ])
    events = []
    team = build_team(specialists_from_config(config), {"perusahaan": "PT Uji", "bidang": "x"}, client=client,
                      on_event=lambda kind, data: events.append((kind, data["agent"])))

    assert team.run("Berapa hak cuti?") == "Hak cuti tahunan 12 hari."
    hrd_call = client.calls[1]
    assert "PT Uji" in hrd_call["system"]
    assert {t["name"] for t in hrd_call["tools"]} == {
        "calculate", "current_time", "list_files", "search_files", "read_document", "read_spreadsheet", "write_file"}
    assert ("delegate", "hrd") in events
    # hasil pencarian HRD diteruskan ke HRD
    hrd_tool_result = client.calls[2]["messages"][2]["content"][0]["content"]  # user, assistant, tool_result
    assert "aturan.txt" in hrd_tool_result


def test_coordinator_prompt_lists_planned_departments(config):
    team = build_team(specialists_from_config(config), COMPANY, client=FakeClient([]))
    assert "PPIC" in team.system_prompt and "hrd" in team.system_prompt


def test_unknown_department_in_config_fails_fast(tmp_path):
    (tmp_path / "x").mkdir()
    cfg = tmp_path / "config.toml"
    cfg.write_text('[departemen.gudang]\nfolder_data = "x"\n', encoding="utf-8")
    with pytest.raises(KeyError):
        specialists_from_config(load_config(cfg))


def test_data_folder_is_read_only_without_output(tmp_path):
    names = {t.name for t in folder_tools(tmp_path)}
    assert "write_file" not in names


def test_sample_hrd_data_is_readable():
    reg = base_registry()
    for tool in folder_tools(ROOT / "contoh_data" / "HRD"):
        reg.register(tool)
    out, err = reg.run("read_document", {"path": "Peraturan_Perusahaan.docx", "start_char": 0})
    assert not err and "Cuti Tahunan" in out
    out, err = reg.run("read_document", {"path": "SOP_Pengajuan_Cuti.pdf", "start_char": 0})
    assert not err and "7 hari" in out
    out, err = reg.run("read_spreadsheet", {"path": "Rekap_Cuti_2026.xlsx", "sheet": "", "contains": "K003",
                                            "start_row": 0, "max_rows": 10})
    assert not err and "Agus Prasetyo" in out
