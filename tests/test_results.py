"""The results writer, the append-only index and schema validation."""

import json

import pytest

from freehand.results import index, layout
from freehand.results.schema import errors, validate
from freehand.results.writer import RunWriter


def test_run_id_and_layout(tmp_path):
    rid = layout.make_run_id("name: x\n")
    assert layout.RUN_ID_RE.match(rid)
    d = layout.episode_dir(tmp_path, "claude-opus-5.5", "rot13", "informed_objective", 10)
    assert d.relative_to(tmp_path).as_posix() == "episodes/claude-opus-5.5/rot13__informed_objective/s10"
    with pytest.raises(ValueError):
        layout.safe("..")


def test_writer_manifest_validates_and_index_is_append_only(tmp_path):
    w = RunWriter(tmp_path, "exp", {"name": "exp"}, "name: exp\n")
    w.manifest["cells"] = [
        {
            "id": "c1",
            "kind": "reference",
            "agent": "oracle",
            "perturbation": "p",
            "arm": "code",
            "seed": 1,
            "suite": "s",
            "status": "planned",
        }
    ]
    w.save()
    w.index_event("started")
    w.update_cell("c1", status="complete")
    w.finish("complete")
    m = json.loads((w.dir / "manifest.json").read_text())
    validate("manifest", m)
    assert m["counts"] == {"complete": 1} and m["status"] == "complete"
    assert m["provenance"]["source_sha256"].startswith("sha256:")
    lines = index.read(tmp_path)
    assert [e["event"] for e in lines] == ["started", "finished"]
    for e in lines:
        validate("index_entry", e)
    assert index.latest(tmp_path)[0]["status"] == "complete"
    with pytest.raises(FileExistsError):
        RunWriter(tmp_path, "exp", {}, "", run_id=w.run_id)


def test_schema_catches_errors():
    assert any("status" in e for e in errors("summary", {"schema": "freehand.episode_summary/1"}))
    bad_turn = {"turn": 0}
    assert errors("turn", bad_turn)
