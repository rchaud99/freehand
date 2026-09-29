"""The one generic experiment runner: config -> verified suites -> ordered cells -> episodes -> results tree.

Every historical one-off script (pilots, ladders, objective/informed/stateless pilots, informed_models, the model
study, the offline controls) is a config in configs/experiments/ run by this module;
docs/provenance/MIGRATION.md maps each.

Stop rules:
  * a per-episode cost cap ends that episode as `capped` (inconclusive, not a failure);
  * a budget refusal (the tag's hard cap) stops that episode as `stopped`, and every cell not yet started becomes
    `not_run_budget`;
  * a provider failure stops that episode as `stopped`; with on_error: stop every cell not yet started becomes
    `not_run_after_error`;
  * Ctrl-C starts no more cells and marks every cell not yet started `not_run_stopped`; the episodes already running
    finish (Ctrl-C again stops waiting for them: they stay `running`, which a resume continues).
Every planned cell stays in the manifest with its final status. `freehand run --resume <run_dir>` re-runs the
stopped ones in place (their logged replies replay at no cost, then the live model continues) and the not-run ones.
A resume uses the run's own config.yaml; a config passed with it must be byte-identical (same config_sha256).
"""
from __future__ import annotations

import hashlib
import json
import random
import threading
import traceback
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import wait as wait_futures
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from freehand import paths
from freehand.agents.arms import CODE_ARM, Arm
from freehand.agents.base import Agent
from freehand.agents.llm_agent import LLMAgent, ResumeAgent
from freehand.agents.reference import make_reference
from freehand.episode import EpisodeConfig, run_episode
from freehand.errors import RunDirError, UsageError
from freehand.experiments.config import Cell, Experiment
from freehand.experiments.fake import fake_policy
from freehand.llm import Budget, EpisodeBudget, Ledger, RequestCache, make_adapter
from freehand.llm.errors import MissingKeyError
from freehand.llm.registry import ModelSpec
from freehand.perturbations.base import Perturbation
from freehand.results import layout
from freehand.results.writer import EpisodeWriter, RunWriter, utc_now
from freehand.suites import caps_problem, data_hash, episode_setup
from freehand.suites.generate import page as suite_page

BALANCE_MARGIN_USD = 1.0        # keep this much of the OpenRouter balance untouched
K1_CHECK_SQUARES = 4            # the `auto` output-mode gate: a no-change check on this many squares ...
K1_MIN_FIRST_TRY = 2            # ... answering in page mm; page_mm if at least this many close first try
DONE = ("complete", "capped")
RESUMABLE = ("stopped", "running")
NOT_RUN = ("planned", "not_run_budget", "not_run_after_error", "not_run_stopped")


class OutputModeCheckStopped(RuntimeError):
    """The K1 output-mode check was cut short, so no mode is decided. The cell is `stopped` (resumable): a resume
    replays the check's logged replies and continues it (the historical `_checked_mode`)."""

    def __init__(self, message: str, stop: dict):
        super().__init__(message)
        self.stop = stop


@dataclass
class RunOptions:
    dry_run: bool = False
    max_usd: float | None = None
    save_images: bool = False
    workers: int | None = None
    fake_models: bool = False
    results_root: Path | None = None
    balance_check: bool | None = None        # None: the config's budget.balance_check


def read_turns(path: Path) -> list[dict]:
    """Logged turns of an episode; a last line cut off by an interrupted process is dropped."""
    out: list[dict] = []
    if not path.exists():
        return out
    with open(path) as f:
        for line in f:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                break
    return out


def logged_state(turns: list[dict]) -> dict:
    """What a resume checks the replay against: the logged strokes (their landed ends) and original cost."""
    return {"strokes": [{"ink_ends": t["stroke"]["ends"]} for t in turns if t.get("stroke")],
            "cost": {"usd_original": sum((t.get("reply") or {}).get("cost_original") or 0 for t in turns)}}


def config_sha256(text: str) -> str:
    """The manifest's `config_sha256` of a config text."""
    return "sha256:" + hashlib.sha256(text.encode()).hexdigest()


class Runner:
    writer: RunWriter
    budget: Budget
    ledger: Ledger
    cache: RequestCache

    def __init__(self, exp: Experiment, opts: RunOptions | None = None):
        self.exp = exp
        self.opts = opts or RunOptions()
        self.root = self.opts.results_root or paths.results_root()
        self.lock = threading.Lock()
        self.halt: str | None = None          # a reason to start no more cells
        self._gate_locks: dict[str, threading.Lock] = {}          # one K1 gate per model, even with workers > 1
        self._gate_failed: dict[str, OutputModeCheckStopped] = {}
        self._started: set[str] = set()       # cells started by this invocation

    @property
    def config_text(self) -> str:
        return self.exp.text or json.dumps(self.exp.raw)

    def workers(self) -> int:
        w = self.opts.workers or self.exp.workers
        if w < 1:
            raise UsageError("--workers must be >= 1")
        if w > 1 and self.exp.budget.episode_cap_mode == "reservation":
            # EpisodeBudget measures an episode's spend as the tag's spend since the episode started, which only
            # equals the episode's own spend when episodes run one at a time.
            raise UsageError(f"{self.exp.name}: budget.episode_cap_mode: reservation needs workers: 1 (got {w})")
        return w

    # ------------------------------------------------------------------ planning
    def ordered_cells(self) -> list[Cell]:
        cells = self.exp.cells()
        refs = [c for c in cells if c.kind == "reference"]
        models = [c for c in cells if c.kind == "model"]
        if self.exp.order == "shuffle":
            random.Random(self.exp.shuffle_seed).shuffle(models)
        return refs + models

    def verify_suites(self) -> dict:
        out: dict[str, dict[str, Any]] = {}
        for b in self.exp.blocks:
            s = b.suite
            if s.id in out:
                out[s.id]["seeds"] = sorted(set(out[s.id]["seeds"]) | set(b.seeds))
                continue
            h, _ = data_hash(s)
            if s.data_hash and h != s.data_hash:
                raise RuntimeError(f"suite {s.id} does not verify: file says {s.data_hash}, generation gives {h}. "
                                   "The frozen data changed; do not run a benchmark on it.")
            problem = caps_problem(s)
            if problem:
                raise RuntimeError(problem + "; do not run a benchmark on it.")
            out[s.id] = {"data_hash": h, "verified": bool(s.data_hash), "version": s.version,
                         "seeds": sorted(b.seeds), "legacy": s.legacy,
                         "episode_caps": {"cap_strokes": s.cap_strokes, "cap_turns": s.cap_turns}}
        return out

    def describe_plan(self) -> dict:
        cells = self.ordered_cells()
        return {"experiment": self.exp.name, "cells": len(cells),
                "reference_cells": sum(c.kind == "reference" for c in cells),
                "model_cells": sum(c.kind == "model" for c in cells),
                "models": {m: s.to_manifest() for m, s in self.exp.models.items()},
                "arms": {a: arm.to_dict() for a, arm in self.exp.arms.items()},
                "budget": vars(self.exp.budget), "suites": self.verify_suites(),
                "cell_ids": [c.id for c in cells]}

    # ------------------------------------------------------------------ budget
    def _open_budget(self) -> dict:
        b = self.exp.budget
        self.cache = RequestCache(paths.cache_path(self.root))
        self.ledger = Ledger(paths.ledger_path(self.root))
        tag = f"fake:{b.tag}" if self.opts.fake_models else b.tag
        spent = self.ledger.spent(tag=tag)
        notes: list[str] = []
        if b.cap_usd is None:                 # no tag cap: --max-usd is the only (per-invocation) cap
            if self.opts.max_usd is None:
                raise UsageError(f"{self.exp.name}: the config sets no budget.cap_usd; pass --max-usd")
            cap = spent + self.opts.max_usd
        else:
            cap = b.cap_usd
            if self.opts.max_usd is not None:
                if spent + self.opts.max_usd < cap:
                    notes.append(f"--max-usd {self.opts.max_usd:.2f}: cap lowered from ${cap:.2f} to "
                                 f"${spent + self.opts.max_usd:.2f} for this invocation")
                cap = min(cap, spent + self.opts.max_usd)
        check = self.exp.budget.balance_check if self.opts.balance_check is None else self.opts.balance_check
        balance = None
        live = any(s.api == "openrouter" for s in self.exp.models.values()) and not self.opts.fake_models
        if check and live and any(c.kind == "model" for c in self.exp.cells()):
            try:
                from freehand.llm.openrouter import spendable
                usable, how = spendable()
                balance = {"usable_usd": usable, "detail": how}
                if usable - BALANCE_MARGIN_USD < cap - spent:
                    new = round(spent + max(0.0, usable - BALANCE_MARGIN_USD), 2)
                    notes.append(f"cap lowered from ${cap:.2f} to ${new:.2f}: {how}")
                    cap = new
            except MissingKeyError as e:
                notes.append(f"balance not checked: {e}")
            except Exception as e:                        # the check is a guard, not a requirement
                notes.append(f"balance check failed ({type(e).__name__}); cap unchanged")
        self.budget = Budget(self.ledger, cap, tag, self.writer.run_id)
        return {"tag": tag, "cap_usd": b.cap_usd, "cap_this_invocation": cap, "max_usd_flag": self.opts.max_usd,
                "episode_cap_usd": b.episode_cap_usd, "episode_cap_mode": b.episode_cap_mode,
                "spent_before": round(spent, 6), "balance": balance, "notes": notes}

    # ------------------------------------------------------------------ agents
    def _spec(self, cell: Cell) -> ModelSpec:
        assert cell.model is not None, f"{cell.id} is not a model cell"
        return self.exp.models[cell.model]

    def _adapter(self, spec: ModelSpec, squares, seed: int, cap: float | None):
        budget: Budget | EpisodeBudget = self.budget
        if cap is not None and self.exp.budget.episode_cap_mode == "reservation":
            budget = EpisodeBudget(self.budget, cap)
        if self.opts.fake_models:
            from freehand.llm.registry import load_registry
            fake = load_registry().resolve("fake")
            return make_adapter(fake, self.cache, budget, policy=fake_policy(squares, seed), salt=spec.id)
        return make_adapter(spec, self.cache, budget)

    def _output_mode(self, cell: Cell, arm: Arm) -> str:
        spec = self._spec(cell)
        mode = arm.output_mode or spec.output_mode
        if mode != "auto":
            return mode
        with self.lock:
            decided = self.writer.manifest["output_modes"].get(spec.id)
            gate = self._gate_locks.setdefault(spec.id, threading.Lock())
        if decided is not None:
            return decided["mode"]
        with gate:                              # the gate runs once per model; concurrent cells wait for its verdict
            with self.lock:
                decided = self.writer.manifest["output_modes"].get(spec.id)
                failed = self._gate_failed.get(spec.id)
            if decided is None:
                if failed is not None:          # cut short earlier in this invocation: do not re-run it here
                    raise OutputModeCheckStopped(str(failed), failed.stop)
                try:
                    decided = self._k1_gate(cell, arm)
                except OutputModeCheckStopped as e:
                    with self.lock:
                        self._gate_failed[spec.id] = e
                    raise
                with self.lock:
                    self.writer.manifest["output_modes"][spec.id] = decided
                self.writer.save()
        return decided["mode"]

    def _k1_gate(self, cell: Cell, arm: Arm) -> dict:
        """The `auto` output mode: a no-change episode on the first 4 squares in page mm; page_mm if >= 2 close on
        the first stroke (the K1 gate of the informed_models design), else crop_px."""
        block = self.exp.blocks[cell.block]
        seed = block.seeds[0]
        squares = suite_page(block.suite, seed)[:K1_CHECK_SQUARES]
        spec = self._spec(cell)
        d = layout.episode_dir(self.writer.dir, spec.agent_name, "check", arm.name, seed)
        cfg = EpisodeConfig(seed=seed, squares=squares, perturbation=Perturbation(seed, name="check"),
                            perturb_after=len(squares), arm=arm, output_mode="page_mm",
                            cap_strokes=block.suite.cap_strokes, cap_turns=block.suite.cap_turns,
                            labels={"run_id": self.writer.run_id, "purpose": "output-mode gate (K1)",
                                    "suite": block.suite.id, "model": spec.id})
        agent: Agent = LLMAgent(self._adapter(spec, squares, seed, None), name=spec.agent_name)
        logged = read_turns(d / "episode.jsonl")
        if logged:                      # an interrupted check: replay its logged replies, then continue it live
            agent = ResumeAgent(agent, [t["reply"] for t in logged])
        s = run_episode(agent, cfg, EpisodeWriter(d, self.opts.save_images))
        if s["stop"]:
            # A cut-short check decides nothing (a late historical fix); the cell stops and can be resumed.
            raise OutputModeCheckStopped(f"{spec.id}: output-mode check stopped ({s['stop']['message'][:80]}); "
                                         "not deciding a mode", s["stop"])
        hits = sum(r["first_try"] for r in s["squares_result"])
        return {"mode": "page_mm" if hits >= K1_MIN_FIRST_TRY else "crop_px",
                "cost": round(s["cost"]["usd_original"], 4),
                "basis": f"no-change check in page mm: {hits}/{len(squares)} first-try closures",
                "episode": str(d.relative_to(self.writer.dir))}

    # ------------------------------------------------------------------ cells
    def _episode_dir(self, cell: Cell) -> Path:
        return layout.episode_dir(self.writer.dir, cell.agent, cell.perturbation, cell.arm, cell.seed)

    def _run_cell(self, cell: Cell, resume_from: tuple[list[dict], dict] | None = None) -> None:
        with self.lock:
            halt = self.halt if resume_from is None else None
            if not halt:
                self._started.add(cell.id)
        if halt:
            self.writer.update_cell(cell.id, status=halt)
            return
        self.writer.update_cell(cell.id, status="running", started_utc=utc_now())
        try:
            self._execute(cell, resume_from)
        except OutputModeCheckStopped as e:
            self.writer.update_cell(cell.id, status="stopped", ended_utc=utc_now(),
                                    stop={"kind": "output_mode_check", "message": str(e),
                                          "check_stop": e.stop})
            self.writer.log(f"{cell.id}: stopped: {e}")
            with self.lock:
                if e.stop.get("kind") == "budget":
                    self.halt = self.halt or "not_run_budget"
                elif self.exp.on_error == "stop":
                    self.halt = self.halt or "not_run_after_error"
        except Exception as e:                      # setup failures (the episode loop catches its own)
            self.writer.update_cell(cell.id, status="error", ended_utc=utc_now(),
                                    stop={"kind": "exception", "message": f"{type(e).__name__}: {e}"})
            self.writer.log(f"ERROR {cell.id}: {type(e).__name__}: {e}\n{traceback.format_exc()}")
            if self.exp.on_error == "stop":
                with self.lock:
                    self.halt = self.halt or "not_run_after_error"

    def _execute(self, cell: Cell, resume_from) -> None:
        block = self.exp.blocks[cell.block]
        suite = block.suite
        st = episode_setup(suite, cell.seed, cell.perturbation, cell.max_squares)
        labels = {"run_id": self.writer.run_id, "experiment": self.exp.name, "cell": cell.id, "suite": suite.id,
                  "suite_data_hash": suite.data_hash, "seed_hash": st.seed_hash, "split": suite.split_of(cell.seed),
                  "perturbation": cell.perturbation, "arm": cell.arm, "model": cell.model,
                  "budget_tag": self.budget.tag, "max_squares": cell.max_squares}
        if cell.kind == "reference":
            agent = make_reference(cell.agent, st.perturbation)
            arm, mode, cap = CODE_ARM, "page_mm", None
            render = cell.render and self.opts.save_images
        else:
            spec = self._spec(cell)
            arm = self.exp.arms[cell.arm]
            mode = self._output_mode(cell, arm)
            cap = cell.episode_cap_usd            # replayed turns count at their original cost (see episode.loop)
            live = LLMAgent(self._adapter(spec, st.squares, cell.seed, cap), name=spec.agent_name)
            agent = ResumeAgent(live, [t["reply"] for t in resume_from[0]]) if resume_from else live
            labels["output_mode_basis"] = "auto (K1 gate)" if (arm.output_mode or spec.output_mode) == "auto" \
                else "configured"
            render = True
        turn_cap = cap if self.exp.budget.episode_cap_mode == "turn" else None
        cfg = EpisodeConfig(seed=cell.seed, squares=st.squares, perturbation=st.perturbation,
                            perturb_after=st.perturb_after, arm=arm, output_mode=mode,
                            cap_strokes=suite.cap_strokes, cap_turns=suite.cap_turns, cost_cap=turn_cap,
                            render=render, labels=labels)
        d = self._episode_dir(cell)
        s = run_episode(agent, cfg, EpisodeWriter(d, self.opts.save_images))
        if resume_from is not None:
            old = resume_from[1]["strokes"]
            if [x["ink_ends"] for x in s["strokes"][:len(old)]] != [x["ink_ends"] for x in old]:
                raise RuntimeError(f"{cell.id}: resumed episode diverged from its log")
        status = s["status"]
        if s["stop"] and s["stop"]["kind"] == "budget":
            with self.lock:
                self.halt = self.halt or "not_run_budget"
        elif status in ("stopped", "error") and self.exp.on_error == "stop":
            with self.lock:
                self.halt = self.halt or "not_run_after_error"
        ft = s["scores"]["first_try"]
        self.writer.update_cell(
            cell.id, status=status, stop=s["stop"], ended_utc=utc_now(),
            episode_dir=str(d.relative_to(self.writer.dir)),
            output_mode=s["output_mode"], cost_usd=s["cost"]["usd"], cost_original_usd=s["cost"]["usd_original"],
            turns=s["turns"], squares_done=len(s["squares_result"]),
            first_try={"hits": ft["hits"], "attempted": ft["attempted"], "planned": ft["planned"]})
        self.writer.log(f"{cell.id}: {status} turns={s['turns']} first-try {ft['hits']}/{ft['attempted']} "
                        f"${s['cost']['usd_original']:.4f}" + (f" [{s['stop']['message'][:100]}]" if s["stop"] else ""))

    # ------------------------------------------------------------------ run
    def _map(self, fn: Callable[[Any], None], jobs: Iterable[Any], workers: int) -> None:
        """Run fn over jobs on `workers` threads. On Ctrl-C: start nothing more, wait for the running jobs (a second
        Ctrl-C stops waiting), then re-raise."""
        ex = ThreadPoolExecutor(max(1, workers))
        futures = [ex.submit(fn, j) for j in jobs]
        try:
            for f in futures:
                f.result()
        except KeyboardInterrupt:
            with self.lock:
                self.halt = "not_run_stopped"
            ex.shutdown(wait=False, cancel_futures=True)
            running = [f for f in futures if not f.done()]
            self.writer.log(f"interrupted: no more cells will start; waiting for {len(running)} running episode(s) "
                            "(Ctrl-C again to stop waiting; they stay `running` and --resume continues them)")
            try:
                wait_futures(running)
            except KeyboardInterrupt:
                self.writer.log("stopped waiting for the running episodes")
            raise
        ex.shutdown(wait=True)

    def _stamp_not_started(self, cells: Iterable[Cell], status: str) -> None:
        """Give the cells this invocation was asked to run, but never started, the halt status."""
        with self.lock:
            todo = [c.id for c in cells if c.id not in self._started]
        for cid in todo:
            self.writer.update_cell(cid, status=status)

    def _start(self, cells: list[Cell]) -> None:
        refs = [c for c in cells if c.kind == "reference"]
        models = [c for c in cells if c.kind == "model"]
        workers = self.workers()
        try:
            self._map(self._run_cell, refs, workers)
            self._map(self._run_cell, models, workers)
        except KeyboardInterrupt:
            self._stamp_not_started(cells, "not_run_stopped")
            raise

    def _final_status(self) -> str:
        cells = self.writer.manifest["cells"]
        states = [c["status"] for c in cells]
        if all(s in DONE for s in states):
            return "complete"
        if any(s == "not_run_stopped" for s in states):
            return "stopped"
        if any(s in DONE for s in states):
            return "partial"
        return "failed"

    def _finish_budget(self) -> None:
        spent_after = self.ledger.spent(tag=self.budget.tag)
        b = self.writer.manifest["budget"]
        b.update({"spent_after": round(spent_after, 6),
                  "spent_this_run": round(self.ledger.spent(run_id=self.writer.run_id), 6)})

    def run(self) -> Path | dict:
        """Run the experiment; returns the run directory (or the plan, for a dry run)."""
        if self.opts.dry_run:
            return self.describe_plan()
        self.workers()                                  # validate before anything is written
        suites = self.verify_suites()
        cells = self.ordered_cells()
        self.writer = RunWriter(self.root, self.exp.name, self.exp.raw, self.config_text)
        m = self.writer.manifest
        m.update({"description": self.exp.description, "preregistration": self.exp.preregistration,
                  "suites": suites, "models": {k: s.to_manifest() for k, s in self.exp.models.items()},
                  "arms": {k: a.to_dict() for k, a in self.exp.arms.items()},
                  "options": {"save_images": self.opts.save_images, "workers": self.opts.workers or self.exp.workers,
                              "fake_models": self.opts.fake_models, "order": self.exp.order,
                              "on_error": self.exp.on_error},
                  "cells": [c.to_manifest() for c in cells]})
        m["budget"] = self._open_budget()
        self.budget.run_id = self.writer.run_id
        self.writer.save()
        self.writer.index_event("started")
        self.writer.log(f"run {self.writer.run_id}: {len(cells)} cells -> {self.writer.dir}")
        for n in m["budget"]["notes"]:
            self.writer.log(f"budget: {n}")
        try:
            self._start(cells)
        finally:
            self._finish_budget()
            self.writer.finish(self._final_status())
        return self.writer.dir

    @staticmethod
    def check_resumable(run_dir: Path) -> dict:
        """The manifest of a run that `resume` can continue; RunDirError otherwise."""
        if not (run_dir / "manifest.json").is_file():
            raise RunDirError(f"{run_dir}: not a run directory (no manifest.json)")
        m = json.loads((run_dir / "manifest.json").read_text())
        if m.get("kind") == "legacy":
            raise RunDirError(f"{run_dir}: an imported historical run; it cannot be resumed (its code is gone)")
        if not (run_dir / "config.yaml").is_file():
            raise RunDirError(f"{run_dir}: no config.yaml; this run cannot be resumed")
        return m

    def resume(self, run_dir: Path) -> Path:
        """Re-run a run's stopped cells in place (logged replies replay free) and its not-run cells.

        The experiment must be the run's own config (the same config_sha256; `load_experiment(run_dir /
        "config.yaml")` gives it), else the cells to resume would be silently mismatched. The run's fake-models
        setting carries over."""
        if self.opts.dry_run:
            raise UsageError("--dry-run cannot be combined with --resume")
        m0 = self.check_resumable(run_dir)
        if config_sha256(self.config_text) != m0.get("config_sha256"):
            raise UsageError(f"{run_dir}: the experiment config differs from the run's own (config_sha256 "
                             f"{m0.get('config_sha256')}); resume without an experiment argument to use its "
                             "config.yaml")
        was_fake = bool((m0.get("options") or {}).get("fake_models"))
        if self.opts.fake_models and not was_fake:
            raise UsageError(f"{run_dir}: this run used real models; --fake-models cannot resume it")
        self.opts.fake_models = was_fake
        self.workers()
        self.writer = RunWriter.reopen(run_dir)
        self.root = self.writer.root
        m = self.writer.manifest
        entry: dict[str, Any] = {"started_utc": utc_now(), "spent_before": None, "cells": []}
        budget_info = self._open_budget()
        self.budget.run_id = self.writer.run_id
        entry["spent_before"] = budget_info["spent_before"]
        entry["budget"] = budget_info
        by_id = {c.id: c for c in self.exp.cells()}
        todo_resume, todo_fresh = [], []
        for mc in m["cells"]:
            cell = by_id.get(mc["id"])
            if cell is None or mc["status"] not in RESUMABLE + NOT_RUN:
                continue
            d = self._episode_dir(cell)
            turns = read_turns(d / "episode.jsonl") if cell.kind == "model" else []
            if turns:           # cut short, or its process died mid-episode: replay the logged replies, continue
                todo_resume.append((cell, (turns, logged_state(turns))))
            else:
                todo_fresh.append(cell)
        entry["cells"] = [c.id for c, _ in todo_resume] + [c.id for c in todo_fresh]
        self.writer.log(f"resume: {len(todo_resume)} stopped episodes, {len(todo_fresh)} not-run cells")
        m["status"] = "running"
        self.writer.save()
        workers = self.workers()
        try:
            try:
                self._map(lambda j: self._run_cell(j[0], j[1]), todo_resume, min(workers, len(todo_resume) or 1))
            except KeyboardInterrupt:
                self._stamp_not_started(todo_fresh, "not_run_stopped")
                raise
            self._start(todo_fresh)
        finally:
            self._finish_budget()
            entry["ended_utc"] = utc_now()
            entry["spent_after"] = m["budget"].get("spent_after")
            m.setdefault("resumes", []).append(entry)
            self.writer.finish(self._final_status())
        return run_dir
