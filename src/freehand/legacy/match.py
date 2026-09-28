"""Which legacy suite (if any) regenerates a historical episode's page and rule exactly."""
from __future__ import annotations

import json

from freehand.suites import list_suites
from freehand.suites.generate import EpisodeSetup, episode_setup

LEGACY_KEYS = ("level", "variant", "knob", "tol", "prompt_extra", "camera_warp", "plotter_offset", "phase")


def _norm(x):
    return json.loads(json.dumps(x))


class SuiteMatcher:
    def __init__(self, suites=None):
        self.suites = [s for s in (suites or list_suites()) if s.legacy]
        self._setups: dict[tuple, EpisodeSetup | None] = {}

    def _setup(self, suite, seed: int, name: str) -> EpisodeSetup | None:
        key = (suite.id, seed, name)
        if key not in self._setups:
            try:
                self._setups[key] = episode_setup(suite, seed, name)
            except RuntimeError:
                self._setups[key] = None
        return self._setups[key]

    @staticmethod
    def _same_rule(ep: dict, desc: dict) -> bool:
        sc = ep.get("scenario")
        if sc:
            return all(_norm(desc.get(k)) == _norm(v) for k, v in sc.items() if k in LEGACY_KEYS)
        if ep.get("family") == "A":
            return desc.get("H1") == ep.get("H1") and desc.get("H2") == ep.get("H2")
        return _norm(desc.get("map_after")) == _norm(ep.get("map_after"))

    def match(self, ep: dict) -> dict | None:
        """{suite, seed_hash, perturbation} if a legacy suite reproduces this episode's squares, change square and
        rule (camera: both poses) exactly; else None."""
        seed = ep["seed"]
        for suite in self.suites:
            if seed not in suite.all_seeds():
                continue
            names = suite.perturbation_names()
            if ep.get("pert") in names:
                names = [ep["pert"]] + [n for n in names if n != ep["pert"]]
            for name in names:
                st = self._setup(suite, seed, name)
                if st is None or st.perturb_after != ep["perturb_after"]:
                    continue
                if [q.to_dict() for q in st.squares] != ep["squares"]:
                    continue
                if self._same_rule(ep, st.perturbation.describe()):
                    return {"suite": suite.id, "suite_data_hash": suite.data_hash, "seed_hash": st.seed_hash,
                            "perturbation": name}
        return None
