"""Run control: resume only with the run's own config, one K1 gate per model under concurrency, Ctrl-C labelling,
budget-mode validation, the per-invocation `episode --max-usd`, pinned suite caps and the CLI's error exits."""

import json
import time

import pytest
import yaml

from freehand import cli
from freehand.errors import FreehandError, RunDirError, UsageError
from freehand.experiments import Runner, RunOptions, load_experiment, parse_experiment
from freehand.experiments import runner as runner_mod
from freehand.suites import caps_problem, load_suite

BASE = {
    "name": "ctl",
    "budget": {"tag": "ctl", "cap_usd": 5.0, "episode_cap_usd": 1.0},
    "workers": 1,
    "models": ["fake"],
    "arms": {"silent": None, "nomemory": None, "informed_objective": None},
    "blocks": [
        {
            "suite": "smoke-v1",
            "seeds": [1],
            "perturbations": ["rot13", "identity"],
            "references": [],
            "arms": ["silent", "nomemory", "informed_objective"],
        }
    ],
}


def _exp(**changes):
    cfg = json.loads(json.dumps(BASE))
    cfg.update(changes)
    return parse_experiment(cfg, yaml.safe_dump(cfg))


def _manifest(d):
    return json.loads((d / "manifest.json").read_text())


# ---------------------------------------------------------------- resume
def test_resume_refuses_a_different_config_and_uses_the_runs_own(results_root):
    d = Runner(_exp(), RunOptions(fake_models=True, max_usd=0.03)).run()
    assert _manifest(d)["status"] != "complete"
    other = _exp(workers=2)  # a different config text
    with pytest.raises(UsageError, match="config differs"):
        Runner(other, RunOptions(fake_models=True)).resume(d)
    with pytest.raises(UsageError, match="dry-run"):
        Runner(_exp(), RunOptions(fake_models=True, dry_run=True)).resume(d)
    # the CLI loads the run's own config.yaml when no experiment is given, and keeps the run's fake-models setting
    assert cli.main(["run", "--resume", str(d), "--max-usd", "2"]) == 0
    assert _manifest(d)["status"] == "complete"
    assert load_experiment(d / "config.yaml").text == (d / "config.yaml").read_text()


def test_resume_cli_rejects_flag_combinations(results_root, capsys):
    d = Runner(_exp(), RunOptions(fake_models=True, max_usd=0.03)).run()
    before = _manifest(d)["status"]
    assert cli.main(["run", "--resume", str(d), "--dry-run"]) == 2
    assert cli.main(["run", "--resume", str(d), "--model", "fake"]) == 2
    assert cli.main(["run", "--resume", str(results_root / "missing")]) == 2
    err = capsys.readouterr().err
    assert "cannot be combined with --resume" in err and "Traceback" not in err
    assert _manifest(d)["status"] == before  # nothing ran


# ---------------------------------------------------------------- K1 gate
def test_k1_gate_runs_once_per_model_with_concurrent_workers(results_root, monkeypatch):
    calls = []
    real = Runner._k1_gate

    def slow_gate(self, cell, arm):
        calls.append(cell.id)
        time.sleep(0.3)  # widen the window in which a second worker could enter
        return real(self, cell, arm)

    monkeypatch.setattr(Runner, "_k1_gate", slow_gate)
    cfg = json.loads(json.dumps(BASE))
    cfg.update(workers=3, models=[{"id": "fake", "output_mode": "auto"}])
    exp = parse_experiment(cfg, yaml.safe_dump(cfg))
    d = Runner(exp, RunOptions(fake_models=True)).run()
    m = _manifest(d)
    assert len(calls) == 1
    assert set(m["output_modes"]) == {"fake"}
    assert m["status"] == "complete" and len(m["cells"]) == 6
    assert len(list(d.glob("episodes/*/check__*/s*/summary.json"))) == 1


# ---------------------------------------------------------------- Ctrl-C
def test_ctrl_c_stamps_every_cell_not_started_and_resume_finishes(results_root, monkeypatch):
    real = Runner._execute
    seen = []

    def interrupt_second(self, cell, resume_from):
        seen.append(cell.id)
        if len(seen) == 2:
            raise KeyboardInterrupt
        return real(self, cell, resume_from)

    monkeypatch.setattr(Runner, "_execute", interrupt_second)
    cfg = json.loads(json.dumps(BASE))
    cfg["blocks"][0]["references"] = ["oracle", "naive", "adaptive"]
    exp = parse_experiment(cfg, yaml.safe_dump(cfg))
    runner = Runner(exp, RunOptions(fake_models=True))
    with pytest.raises(KeyboardInterrupt):
        runner.run()
    d = runner.writer.dir
    m = _manifest(d)
    states = [c["status"] for c in m["cells"]]
    assert "planned" not in states
    assert states.count("running") == 1  # the interrupted episode: resumable
    assert set(states) <= {"complete", "running", "not_run_stopped"}
    assert all(c["status"] == "not_run_stopped" for c in m["cells"] if c["kind"] == "model")
    assert m["status"] == "stopped"
    monkeypatch.setattr(Runner, "_execute", real)
    Runner(exp, RunOptions(fake_models=True)).resume(d)
    assert _manifest(d)["status"] == "complete"


# ---------------------------------------------------------------- budgets
def test_reservation_episode_caps_need_one_worker():
    cfg = json.loads(json.dumps(BASE))
    cfg["budget"]["episode_cap_mode"] = "reservation"
    cfg["workers"] = 2
    with pytest.raises(ValueError, match="reservation needs workers: 1"):
        parse_experiment(cfg, yaml.safe_dump(cfg))
    cfg["workers"] = 1
    exp = parse_experiment(cfg, yaml.safe_dump(cfg))
    with pytest.raises(UsageError, match="reservation needs workers: 1"):
        Runner(exp, RunOptions(fake_models=True, workers=2)).run()


def test_episode_max_usd_caps_each_invocation_not_the_tag(results_root):
    args = [
        "episode",
        "--model",
        "fake",
        "--suite",
        "smoke-v1",
        "--seed",
        "1",
        "--perturbation",
        "rot13",
        "--arm",
        "silent",
        "--fake-models",
        "--max-usd",
        "0.02",
    ]
    cli.main(args)
    time.sleep(1.1)  # run ids have one-second resolution
    cli.main(args)
    runs = sorted((results_root / "adhoc").iterdir())
    assert len(runs) == 2
    spent = [_manifest(d)["budget"]["spent_this_run"] for d in runs]
    assert all(0 < s <= 0.02 for s in spent)  # the second invocation could still spend its own $0.02
    assert _manifest(runs[1])["budget"]["cap_this_invocation"] == pytest.approx(
        _manifest(runs[1])["budget"]["spent_before"] + 0.02
    )


def test_a_config_without_a_tag_cap_needs_max_usd(results_root):
    cfg = json.loads(json.dumps(BASE))
    cfg["budget"]["cap_usd"] = None
    exp = parse_experiment(cfg, yaml.safe_dump(cfg))
    with pytest.raises(UsageError, match="--max-usd"):
        Runner(exp, RunOptions(fake_models=True)).run()


# ---------------------------------------------------------------- suites
def test_frozen_suite_caps_are_pinned(monkeypatch):
    s = load_suite("core-v1")
    assert caps_problem(s) is None
    changed = type(s)(**{**{f: getattr(s, f) for f in s.__dataclass_fields__}, "cap_strokes": 13})
    assert "pinned at (12, 14)" in caps_problem(changed)
    monkeypatch.setattr(runner_mod, "caps_problem", lambda suite: "caps changed")
    with pytest.raises(RuntimeError, match="caps changed"):
        Runner(_exp()).verify_suites()


# ---------------------------------------------------------------- CLI errors
@pytest.mark.parametrize(
    "cmd",
    [["replay"], ["validate"], ["report"], ["figures", "--out", "x"], ["rescore"], ["quote-bank", "--out", "x.csv"]],
)
def test_commands_on_a_missing_or_empty_run_dir_exit_2(cmd, tmp_path, capsys):
    empty = tmp_path / "empty"
    empty.mkdir()
    (tmp_path / "norun").mkdir()
    (tmp_path / "norun" / "manifest.json").write_text("{}")
    for target, why in (
        (tmp_path / "missing", "no such directory"),
        (empty, "no manifest.json"),
        (tmp_path / "norun", "no episodes"),
    ):
        assert cli.main([cmd[0], str(target), *cmd[1:]]) == 2
        err = capsys.readouterr().err
        assert why in err and "Traceback" not in err


def test_expected_errors_are_one_line_with_their_exit_code(monkeypatch, capsys):
    class Boom(FreehandError):
        exit_code = 7

    def fail(a):
        raise Boom("clear message")

    monkeypatch.setattr(cli, "cmd_balance", fail)
    assert cli.main(["balance"]) == 7
    assert capsys.readouterr().err.strip() == "freehand: error: clear message"
    monkeypatch.setattr(cli, "cmd_balance", lambda a: (_ for _ in ()).throw(RunDirError("nope")))
    assert cli.main(["balance"]) == 2
    assert cli.main(["run", "no-such-experiment"]) == 2
    assert "no experiment config" in capsys.readouterr().err
