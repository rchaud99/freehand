"""The `freehand` command line.

    freehand models                         the model registry
    freehand suite list|show|verify|freeze|scan|render
    freehand run <experiment> [--dry-run] [--max-usd X] [--fake-models] [--save-images]
    freehand run --resume RUN_DIR [--max-usd X]     (the run's own config.yaml)
    freehand episode --model <id or vendor/slug> --suite <s> --seed <n> [--perturbation p] [--arm a] ...
    freehand report <run_dir> [<run_dir> ...]
    freehand replay <run_dir> [--render]
    freehand validate <run_dir>
    freehand import-legacy --source NAME=PATH [...] [--exclude GLOB] [--only GLOB] [--merge-cache]
    freehand ls [--experiment X] [--legacy]
    freehand balance
    freehand quote-bank <run_dir> [...] --out FILE.csv
    freehand rescore <run_dir> [...]
    freehand figures <run_dir> [...] --out DIR [--scorer corrected|legacy]

Exit codes: 0 success; 1 a check failed (replay mismatch, schema error, suite hash); 2 bad input (arguments, a
missing or empty run directory, an invalid config); 3 a run ended with cells not complete; 130 interrupted.
Expected errors print one line, no traceback (freehand.errors).
"""
from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path

import yaml

from freehand import __version__, paths
from freehand.errors import EXIT_CHECK_FAILED, EXIT_INCOMPLETE, EXIT_INTERRUPTED, EXIT_USAGE, FreehandError, UsageError


def _print_json(obj) -> None:
    print(json.dumps(obj, indent=1, default=str))


def _table(rows: list[dict], cols: list[str]) -> str:
    if not rows:
        return "(none)"
    w = {c: max(len(c), *(len(str(r.get(c, ""))) for r in rows)) for c in cols}
    lines = ["  ".join(c.ljust(w[c]) for c in cols), "  ".join("-" * w[c] for c in cols)]
    lines += ["  ".join(str(r.get(c, "")).ljust(w[c]) for c in cols) for r in rows]
    return "\n".join(lines)


# ---------------------------------------------------------------- models
def cmd_models(a) -> int:
    from freehand.llm.registry import load_registry
    reg = load_registry()
    rows = [{"id": m.id, "slug": m.slug, "api": m.api, "provider": m.provider or "auto",
             "reasoning": json.dumps(m.reasoning or m.settings), "max_tokens": m.max_tokens,
             "$/Mtok in/out": f"{m.price_in:g}/{m.price_out:g}", "output": m.output_mode, "added": m.added}
            for m in reg.models.values()]
    if a.json:
        _print_json({m.id: m.to_manifest() | {"notes": m.notes} for m in reg.models.values()})
    else:
        print(_table(rows, list(rows[0])))
        print("\nAny other OpenRouter slug (vendor/model) also works, with the [defaults] of configs/models.toml.")
    return 0


# ---------------------------------------------------------------- suites
def cmd_suite(a) -> int:
    from freehand import suites as S
    from freehand.suites.generate import freeze, scan_seeds
    if a.suite_cmd == "list":
        rows = [{"id": s.id, "track": s.track, "rules": len(s.perturbations), "dev": len(s.seeds["dev"]),
                 "test": len(s.seeds["test"]), "legacy": s.legacy, "frozen": bool(s.data_hash)}
                for s in S.list_suites()]
        print(_table(rows, list(rows[0])))
        return 0
    if a.suite_cmd == "verify":
        targets = S.list_suites() if a.all or not a.suites else [S.load_suite(x) for x in a.suites]
        bad = 0
        for s in targets:
            h, _ = S.data_hash(s)
            caps = S.caps_problem(s)
            ok = h == s.data_hash and caps is None
            bad += not ok
            line = f"{s.id:22s} {'OK' if ok else 'MISMATCH'}  {h}" + (f"  {caps}" if caps else "")
            if a.oracle:
                fails = {seed: [k for k, v in S.oracle_check(s, seed).items() if not v] for seed in s.all_seeds()}
                fails = {k: v for k, v in fails.items() if v}
                line += "  oracle: all reachable" if not fails else f"  oracle: UNREACHABLE {fails}"
                bad += bool(fails) and not s.legacy
            print(line)
        return EXIT_CHECK_FAILED if bad else 0
    s = S.load_suite(a.suite)
    if a.suite_cmd == "show":
        if a.seed is None:
            print(yaml.safe_dump({"id": s.id, "version": s.version, "track": s.track, "description": s.description,
                                  "page": vars(s.page), "change": {"schedule": s.schedule, "after": s.change_after},
                                  "perturbations": s.perturbations, "seeds": s.seeds, "data_hash": s.data_hash},
                                 sort_keys=False, width=110))
        else:
            d = S.seed_data(s, a.seed)
            d["page"] = [{k: q[k] for k in ("idx", "x0", "y0", "side", "missing", "open_ends")} for q in d["page"]]
            d["seed_hash"] = S.seed_hash(s, a.seed)
            _print_json(d)
        return 0
    if a.suite_cmd == "freeze":
        print(f"{s.id}: {freeze(s)}")
        return 0
    if a.suite_cmd == "scan":
        print(scan_seeds(s, a.start, a.count))
        return 0
    if a.suite_cmd == "render":
        import cv2

        from freehand.episode.world import World
        st = S.episode_setup(s, a.seed, a.perturbation or s.perturbation_names()[0])
        w = World(a.seed, st.squares, st.perturbation, st.perturb_after)
        cv2.imwrite(a.out, w.render(st.squares[0]))
        print(a.out)
        return 0
    return 2


# ---------------------------------------------------------------- run / episode
def _run_options(a):
    from freehand.experiments import RunOptions
    return RunOptions(dry_run=a.dry_run, max_usd=a.max_usd, save_images=a.save_images, workers=a.workers,
                      fake_models=a.fake_models, balance_check=False if a.no_balance_check else None)


def cmd_run(a) -> int:
    from freehand.experiments import Runner, load_experiment
    if a.resume:
        if a.dry_run:
            raise UsageError("--dry-run cannot be combined with --resume")
        if a.model or a.split:
            raise UsageError("--model and --split cannot be combined with --resume (the run's config fixes them)")
        run_dir = Path(a.resume)
        Runner.check_resumable(run_dir)
        exp = load_experiment(a.experiment or run_dir / "config.yaml")
        d = Runner(exp, _run_options(a)).resume(run_dir)
        return _run_result(d)
    if not a.experiment:
        raise UsageError("give an experiment (a name in configs/experiments/ or a path), or --resume RUN_DIR")
    exp = load_experiment(a.experiment, models=a.model or None, split=a.split)
    out = Runner(exp, _run_options(a)).run()
    if isinstance(out, dict):
        plan = out
        print(f"experiment {plan['experiment']}: {plan['cells']} cells ({plan['reference_cells']} reference, "
              f"{plan['model_cells']} model); no credentials read, no calls made")
        for sid, info in plan["suites"].items():
            print(f"  suite {sid}: {info['data_hash']} ({'verified' if info['verified'] else 'NOT FROZEN'}), "
                  f"seeds {info['seeds']}")
        for mid, m in plan["models"].items():
            print(f"  model {mid}: {m['slug']} via {m['api']}/{m['provider']}, reasoning {m['reasoning']}, "
                  f"max_tokens {m['max_tokens']}, output {m['output_mode']}")
        cap = plan["budget"]["cap_usd"]
        print(f"  budget: tag {plan['budget']['tag']}, "
              + (f"cap ${cap:.2f}" if cap is not None else "no tag cap (--max-usd per invocation)")
              + f", episode cap {plan['budget']['episode_cap_usd']}")
        if a.verbose:
            for c in plan["cell_ids"]:
                print("   ", c)
        return 0
    return _run_result(out)


def _run_result(d: Path) -> int:
    print(d)
    m = json.loads((Path(d) / "manifest.json").read_text())
    print(f"status {m['status']}; cells {m['counts']}; spent this run ${m['budget'].get('spent_this_run', 0):.4f}")
    return 0 if m["status"] == "complete" else EXIT_INCOMPLETE


def cmd_episode(a) -> int:
    """An ad-hoc episode of any model (registered id or any OpenRouter slug), through the same runner."""
    from freehand.experiments import Runner
    from freehand.experiments.config import parse_experiment
    from freehand.suites import load_suite
    suite = load_suite(a.suite)
    pert = a.perturbation or suite.perturbation_names()[0]
    model: dict = {"id": a.model}
    for k in ("output_mode", "max_tokens"):
        if getattr(a, k) is not None:
            model[k] = getattr(a, k)
    if a.reasoning:
        model["reasoning"] = json.loads(a.reasoning)
    # No tag cap: --max-usd caps this invocation's new spend (as for `run`), not the tag's lifetime spend.
    d = {"name": a.name, "description": f"ad-hoc episode: {a.model} on {suite.id} seed {a.seed} {pert} {a.arm}",
         "budget": {"tag": a.tag, "cap_usd": None, "episode_cap_usd": a.episode_cap},
         "workers": 1, "models": [model], "arms": {a.arm: None},
         "blocks": [{"suite": suite.id, "seeds": [a.seed], "perturbations": [pert], "references": a.references or [],
                     "arms": [a.arm], "max_squares": a.max_squares}]}
    text = yaml.safe_dump(d, sort_keys=False)
    exp = parse_experiment(d, text)
    out = Runner(exp, _run_options(a)).run()
    if isinstance(out, dict):
        _print_json(out)
        return 0
    m = json.loads((Path(out) / "manifest.json").read_text())
    cell = next(c for c in m["cells"] if c["kind"] == "model")
    print(out)
    print(f"{cell['status']}: {cell.get('turns')} turns, first-try {cell.get('first_try')}, "
          f"${cell.get('cost_original_usd', 0):.4f}"
          + (f" [{cell['stop']['message'][:120]}]" if cell.get("stop") else ""))
    return 0 if cell["status"] in ("complete", "capped") else EXIT_INCOMPLETE


# ---------------------------------------------------------------- analysis
def _run_dirs(names: list[str]) -> list[Path]:
    """Every argument must be a run directory with a manifest and at least one episode (else exit 2)."""
    from freehand.results.layout import require_run_dir
    return [require_run_dir(x) for x in names]


def cmd_report(a) -> int:
    from freehand.analysis.report import write_report
    out = write_report(_run_dirs(a.run_dirs), Path(a.out) if a.out else None)
    print(out)
    return 0


def cmd_replay(a) -> int:
    from freehand.replay import replay_run
    run_dir = _run_dirs([a.run_dir])[0]
    r = replay_run(run_dir, render=a.render, limit=a.limit, image_dir=Path(a.images) if a.images else None)
    _print_json({k: v for k, v in r.items() if k != "inexact"} | {"inexact": r["inexact"][:20]})
    return 0 if not r["errors"] and not r["inexact"] else EXIT_CHECK_FAILED


def cmd_validate(a) -> int:
    from freehand.results.schema import validate_run
    errs = validate_run(_run_dirs([a.run_dir])[0])
    for e in errs[:50]:
        print(e)
    print(f"{len(errs)} schema error(s)")
    return EXIT_CHECK_FAILED if errs else 0


def cmd_import_legacy(a) -> int:
    from freehand.legacy import Importer
    sources = {}
    for s in a.source:
        name, _, path = s.partition("=")
        if not path:
            raise UsageError(f"--source must be NAME=PATH, got {s!r}")
        p = Path(path).expanduser().resolve()
        if not p.is_dir():
            raise UsageError(f"--source {name}: {p} is not a directory")
        sources[name] = p
    imp = Importer(sources, hash_images=not a.no_image_hashes, exclude=a.exclude, only=a.only, force=a.force)
    if not a.cache_only:
        print(imp.import_all())
    if a.merge_cache or a.cache_only:
        for r in imp.merge_caches():
            print(r)
    return 0


def cmd_ls(a) -> int:
    from freehand.results import index
    rows = []
    for e in index.latest():
        if a.experiment and e.get("experiment") != a.experiment:
            continue
        if (e.get("kind") == "legacy") != a.legacy and not a.all:
            continue
        rows.append({"run": e.get("run_id") or "", "experiment": e.get("experiment"), "status": e.get("status"),
                     "cells": e.get("cells"), "counts": json.dumps(e.get("counts") or {}),
                     "spend": "" if e.get("spend_usd") is None else f"${e['spend_usd']:.2f}"
                     + (" (simulated)" if e.get("fake_models") else ""), "path": e.get("path"),
                     "ts": e.get("ts")})
    print(_table(rows, ["ts", "experiment", "run", "status", "cells", "counts", "spend", "path"]))
    print(f"\nresults root: {paths.results_root()}")
    return 0


def cmd_balance(a) -> int:
    from freehand.llm.openrouter import spendable
    usable, how = spendable()
    print(f"spendable ${usable:.2f} ({how})")
    return 0


def cmd_quote_bank(a) -> int:
    from freehand.analysis.quote_bank import write_quote_bank
    n = write_quote_bank(_run_dirs(a.run_dirs), Path(a.out), tuple(a.fields.split(",")))
    print(f"{n} rows -> {a.out}")
    return 0


def cmd_rescore(a) -> int:
    from freehand.analysis.rescore import rescore_runs
    table = rescore_runs(_run_dirs(a.run_dirs))
    print(table["markdown"])
    if a.out:
        Path(a.out).write_text(json.dumps(table["rows"], indent=1))
    return 0


def cmd_figures(a) -> int:
    from freehand.analysis.figures import write_figures
    _print_json(write_figures(_run_dirs(a.run_dirs), Path(a.out), a.scorer, a.arm))
    return 0


# ---------------------------------------------------------------- parser
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="freehand", description="Freehand: learning a silently changed tool.")
    p.add_argument("--version", action="version", version=f"freehand {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    m = sub.add_parser("models", help="list the model registry")
    m.add_argument("--json", action="store_true")
    m.set_defaults(fn=cmd_models)

    s = sub.add_parser("suite", help="inspect, verify, freeze or build suites")
    ss = s.add_subparsers(dest="suite_cmd", required=True)
    ss.add_parser("list")
    v = ss.add_parser("verify", help="recompute data hashes (and optionally oracle reachability)")
    v.add_argument("suites", nargs="*")
    v.add_argument("--all", action="store_true")
    v.add_argument("--oracle", action="store_true", help="also check that the oracle reaches every target")
    sh = ss.add_parser("show")
    sh.add_argument("suite")
    sh.add_argument("--seed", type=int)
    fr = ss.add_parser("freeze", help="write the data hash into the suite file")
    fr.add_argument("suite")
    sc = ss.add_parser("scan", help="first feasible seeds from --start (for building a new suite)")
    sc.add_argument("suite")
    sc.add_argument("--start", type=int, required=True)
    sc.add_argument("--count", type=int, default=10)
    rn = ss.add_parser("render", help="render a seed's first view to a PNG")
    rn.add_argument("suite")
    rn.add_argument("--seed", type=int, required=True)
    rn.add_argument("--perturbation")
    rn.add_argument("--out", required=True)
    s.set_defaults(fn=cmd_suite)

    def run_flags(x, max_usd_default=None):
        x.add_argument("--dry-run", action="store_true", help="print the plan; read no credentials, make no calls")
        x.add_argument("--max-usd", type=float, default=max_usd_default,
                       help="hard cap on new spend for this invocation")
        x.add_argument("--save-images", action="store_true", help="also save every observation PNG")
        x.add_argument("--workers", type=int)
        x.add_argument("--fake-models", action="store_true", help="replace every model by the offline fake")
        x.add_argument("--no-balance-check", action="store_true")
        x.add_argument("-v", "--verbose", action="store_true")

    r = sub.add_parser("run", help="run an experiment config")
    r.add_argument("experiment", nargs="?",
                   help="configs/experiments/<name>.yaml or a path (optional with --resume: the run's config.yaml)")
    r.add_argument("--resume", metavar="RUN_DIR", help="re-run the stopped and not-run cells of a run in place, "
                   "with the run's own config")
    r.add_argument("--model", action="append", metavar="ID_OR_SLUG",
                   help="run these models instead of the config's (repeatable; any OpenRouter slug works)")
    r.add_argument("--split", choices=["dev", "test", "all"], help="run every block on this seed split")
    run_flags(r)
    r.set_defaults(fn=cmd_run)

    e = sub.add_parser("episode", help="one ad-hoc episode of any model")
    e.add_argument("--model", required=True, help="registry id (see `freehand models`) or any OpenRouter slug")
    e.add_argument("--suite", required=True)
    e.add_argument("--seed", type=int, required=True)
    e.add_argument("--perturbation")
    e.add_argument("--arm", default="informed_objective")
    e.add_argument("--output-mode", choices=["page_mm", "crop_px", "auto"])
    e.add_argument("--max-tokens", type=int)
    e.add_argument("--reasoning", help='JSON OpenRouter reasoning object, e.g. \'{"effort": "high"}\'')
    e.add_argument("--max-squares", type=int)
    e.add_argument("--episode-cap", type=float, help="per-episode cost cap (status `capped`)")
    e.add_argument("--references", nargs="*", help="also run these reference agents on the same episode")
    e.add_argument("--tag", default="adhoc", help="budget tag (spend is capped per tag)")
    e.add_argument("--name", default="adhoc", help="results/<name>/<run_id>")
    run_flags(e, max_usd_default=2.0)          # --max-usd caps this invocation's new spend (default $2)
    e.set_defaults(fn=cmd_episode)

    rp = sub.add_parser("report", help="summary tables and charts for one or more runs")
    rp.add_argument("run_dirs", nargs="+")
    rp.add_argument("--out", help="output directory (default: <last run>/report)")
    rp.set_defaults(fn=cmd_report)

    rl = sub.add_parser("replay", help="re-simulate a run's logged commands (and optionally its images)")
    rl.add_argument("run_dir")
    rl.add_argument("--render", action="store_true", help="also regenerate every observation and check its sha256")
    rl.add_argument("--images", help="write the regenerated images here")
    rl.add_argument("--limit", type=int)
    rl.set_defaults(fn=cmd_replay)

    va = sub.add_parser("validate", help="check a run directory against the results JSON Schemas")
    va.add_argument("run_dir")
    va.set_defaults(fn=cmd_validate)

    il = sub.add_parser("import-legacy", help="index historical runs into results/legacy/ (never moves originals)")
    il.add_argument("--source", action="append", required=True, metavar="NAME=PATH",
                    help="a historical copy (repeatable; earlier sources are canonical for duplicates)")
    il.add_argument("--exclude", action="append", default=[], metavar="GLOB", help="skip runs whose name matches")
    il.add_argument("--only", action="append", default=[], metavar="GLOB", help="import only matching runs")
    il.add_argument("--merge-cache", action="store_true", help="also merge each source's cache.sqlite + spend")
    il.add_argument("--cache-only", action="store_true", help="only merge the caches")
    il.add_argument("--no-image-hashes", action="store_true", help="do not hash the original PNGs")
    il.add_argument("--force", action="store_true", help="re-convert runs already imported")
    il.set_defaults(fn=cmd_import_legacy)

    ls = sub.add_parser("ls", help="list runs from the global index")
    ls.add_argument("--experiment")
    ls.add_argument("--legacy", action="store_true", help="list imported historical runs instead")
    ls.add_argument("--all", action="store_true")
    ls.set_defaults(fn=cmd_ls)

    b = sub.add_parser("balance", help="OpenRouter balance and key limit")
    b.set_defaults(fn=cmd_balance)

    q = sub.add_parser("quote-bank", help="extract notes, memory and reasoning from runs into a CSV")
    q.add_argument("run_dirs", nargs="+")
    q.add_argument("--out", required=True, help="CSV file (gzip-compressed if it ends in .gz)")
    q.add_argument("--fields", default="note,memory,thoughts",
                   help="comma-separated: which texts to scan (note, memory, thoughts = reasoning summaries)")
    q.set_defaults(fn=cmd_quote_bank)

    rs = sub.add_parser("rescore", help="old vs corrected first-try scores of (legacy) runs")
    rs.add_argument("run_dirs", nargs="+")
    rs.add_argument("--out")
    rs.set_defaults(fn=cmd_rescore)

    fg = sub.add_parser("figures", help="study figures: learning-curve grid, first-try bars, all-arms curves, table")
    fg.add_argument("run_dirs", nargs="+", help="runs to combine (the first run wins on identical repeats)")
    fg.add_argument("--out", required=True)
    fg.add_argument("--scorer", choices=["corrected", "legacy"], default="corrected",
                    help="legacy = the historical per-square-results scorer (for parity with old reports)")
    fg.add_argument("--arm", default="informed_objective", help="the arm of the grid, bars and table")
    fg.set_defaults(fn=cmd_figures)
    return p


def _message(e: BaseException) -> str:
    if isinstance(e, KeyError) and len(e.args) == 1 and isinstance(e.args[0], str):
        return e.args[0]                                  # str(KeyError) would add quotes
    return str(e)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    with warnings.catch_warnings():
        warnings.simplefilter("default")
        try:
            return int(args.fn(args) or 0)
        except FreehandError as e:
            print(f"freehand: error: {_message(e)}", file=sys.stderr)
            return e.exit_code
        except (FileNotFoundError, FileExistsError, KeyError, ValueError) as e:   # invalid configs, unknown names
            print(f"freehand: error: {_message(e)}", file=sys.stderr)
            return EXIT_USAGE
        except KeyboardInterrupt:
            print("freehand: interrupted", file=sys.stderr)
            return EXIT_INTERRUPTED


if __name__ == "__main__":
    raise SystemExit(main())
