"""Run Freehand A: models and code references on seeded worlds, in parallel, under one hard spend cap.

results/camera3d/<run_id>/<agent>/s<seed>/  (see episode.py), plus run.json with the plan and the summaries.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from freehand import paths
from freehand.camera3d.agents import ToolModel, reference
from freehand.camera3d.chat import ToolChat
from freehand.camera3d.env import Spec
from freehand.camera3d.episode import run_episode
from freehand.llm.ledger import Budget, Ledger
from freehand.llm.registry import load_registry

TAG = "camera3d"
SEEDS = (3004, 3017, 3008, 3023, 3033, 3015)  # placeable, and the camera move shifts the view by 40+ mm
REFERENCES = ("oracle", "estimator")


def _environment() -> dict:
    """What produced the data: the code version and the libraries that affect rendering and requests."""
    import platform
    import subprocess
    from importlib import metadata

    def git(*args):
        try:
            return subprocess.run(["git", *args], cwd=paths.repo_root(), capture_output=True, text=True).stdout.strip()
        except OSError:
            return None

    return {
        "git_commit": git("rev-parse", "HEAD"),
        "git_dirty": bool(git("status", "--porcelain")),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "packages": {k: metadata.version(k) for k in ("numpy", "opencv-python-headless", "requests") if _has(k)},
    }


def _snapshot_code(dest: Path) -> None:
    """The package source, prompts and model registry exactly as run (the working copy may be uncommitted)."""
    import tarfile

    root = paths.repo_root()
    with tarfile.open(dest, "w:gz") as tar:
        tar.add(
            root / "src" / "freehand",
            arcname="src/freehand",
            filter=lambda ti: None if "__pycache__" in ti.name else ti,
        )
        tar.add(root / "configs" / "models.toml", arcname="configs/models.toml")


def _has(dist: str) -> bool:
    from importlib import metadata

    try:
        metadata.version(dist)
        return True
    except metadata.PackageNotFoundError:
        return False


def run(
    models: list[str],
    seeds: list[int],
    cap_usd: float,
    episode_cap_usd: float,
    spec_kw: dict | None = None,
    references: tuple = REFERENCES,
    workers: int = 8,
    out_root: Path | None = None,
    log=print,
    arms: tuple = ("transfer",),
    fresh_cap_usd: float | None = None,
    study: str | None = None,
    prereg: Path | None = None,
) -> Path:
    """Run every agent on every seed in each arm (`transfer`, `fresh`). Jobs go page by page, so if the budget runs
    out it is the last pages that are incomplete. run.json holds the plan, the environment, the preregistration
    snapshot (if given) and, as episodes finish, their summaries."""
    spec_kw = dict(spec_kw or {})
    if spec_kw.pop("fresh", False):  # the older calling convention: fresh as a spec setting
        arms = ("fresh",)
    run_id = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-" + uuid.uuid4().hex[:6]
    out = (out_root or paths.results_root() / TAG) / run_id
    out.mkdir(parents=True)
    reg = load_registry()
    specs = {m: reg.resolve(m) for m in models}
    ledger = Ledger(paths.ledger_path())
    budget = Budget(ledger, cap_usd + ledger.spent(tag=TAG), TAG, run_id)  # the cap is on this run's new spend
    plan: dict = {
        "run_id": run_id,
        "study": study,
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "models": {m: s.to_manifest() for m, s in specs.items()},
        "references": list(references),
        "seeds": list(seeds),
        "arms": list(arms),
        "spec": Spec(0, **spec_kw).to_dict() | {"seed": None, "fresh": None},
        "cap_usd": cap_usd,
        "episode_cap_usd": {"transfer": episode_cap_usd, "fresh": fresh_cap_usd or episode_cap_usd},
        "environment": _environment(),
        "results": [],
    }
    if prereg is not None:
        import hashlib

        text = Path(prereg).read_text()
        plan["preregistration"] = {
            "file": str(prereg),
            "sha256": hashlib.sha256(text.encode()).hexdigest(),
            "text": text,
        }
    _snapshot_code(out / "code_snapshot.tar.gz")
    lock = threading.Lock()

    def save():
        (out / "run.json").write_text(json.dumps(plan, indent=1))

    save()

    def one(job):
        name, seed, arm = job
        fresh = arm == "fresh"
        spec = Spec(seed, **spec_kw, fresh=fresh)
        cap = (fresh_cap_usd or episode_cap_usd) if fresh else episode_cap_usd
        if name in specs:
            agent = ToolModel(ToolChat(specs[name], budget, run_id, cap), spec.n_episode_squares, spec.cap_strokes)
        else:
            agent = reference(name)
        folder = out / agent.name / (f"s{seed}_fresh" if fresh else f"s{seed}")
        try:
            summ = run_episode(spec, agent, folder, log=log)["summary"]
        except Exception as e:  # one failed episode must not kill the others
            log(f"[{name} s{seed} {arm}] FAILED: {type(e).__name__}: {e}")
            summ = {"status": "failed", "error": f"{type(e).__name__}: {e}"}
        with lock:
            plan["results"].append(
                {"agent": agent.name, "seed": seed, "arm": arm, "dir": str(folder.relative_to(out)), **summ}
            )
            plan["spent_usd"] = round(ledger.spent(tag=TAG, run_id=run_id), 4)
            save()
        return summ

    jobs = [(a, s, arm) for s in seeds for arm in arms for a in (*references, *models)]
    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(one, jobs))
    plan["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    plan["spent_usd"] = round(ledger.spent(tag=TAG, run_id=run_id), 4)
    save()
    log(f"run {run_id}: spent ${plan['spent_usd']:.2f}; {out}")
    return out
