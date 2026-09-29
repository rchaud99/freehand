"""Reference (code) agents and the factory that pairs a reference name with a perturbation.

Names (the same across rules; the implementation depends on the rule, exactly as in the historical runs):
  oracle            knows the hidden rule (always subject to ink noise and the reachable region)
  naive             never adapts
  adaptive          the ideal estimator: fits the rule's model family from its own marks (privileged)
  local_patcher     offset patcher: corrects by the last miss on the current square, forgets between squares
  local_broyden     Broyden secant within a target, numeric observations only
  adaptive_library  library learner over numeric observations: detects a change, selects a rule family
  family_estimator  knows the family and change time; learns its parameters (discriminating rules only)
"""

from __future__ import annotations

from freehand.agents.base import Agent
from freehand.agents.reference.camera import CamAdaptive, CamNaive, CamOracle
from freehand.agents.reference.levels import LAdaptive, LNaive, LOracle
from freehand.agents.reference.local import FamilyEstimator, LocalPatcher
from freehand.agents.reference.numeric import AdaptiveLibrary, LocalBroyden, NumericAgent
from freehand.agents.reference.plotter_map import AdaptiveAgent, NaiveAgent, OracleAgent
from freehand.perturbations.base import Perturbation
from freehand.perturbations.discriminating import FAMILY_OF_TYPE

REFERENCE_NAMES = (
    "oracle",
    "naive",
    "adaptive",
    "local_patcher",
    "local_broyden",
    "adaptive_library",
    "family_estimator",
)
DEFAULT_REFERENCES = ("oracle", "naive", "adaptive")


def make_reference(name: str, perturbation: Perturbation) -> Agent:
    """A fresh reference agent `name` for an episode under `perturbation`."""
    if name not in REFERENCE_NAMES:
        raise KeyError(f"unknown reference agent {name!r}; known: {REFERENCE_NAMES}")
    p = perturbation
    if name == "local_patcher":
        return LocalPatcher()
    if name == "local_broyden":
        return NumericAgent(LocalBroyden())
    if name == "adaptive_library":
        return NumericAgent(AdaptiveLibrary())
    if name == "family_estimator":
        fam = FAMILY_OF_TYPE.get(p.type_name)
        if fam is None:
            raise ValueError(f"family_estimator needs a discriminating rule, not {p.type_name}")
        return FamilyEstimator(fam)
    if p.family == "camera":
        return {"oracle": CamOracle, "naive": CamNaive, "adaptive": CamAdaptive}[name]()
    if p.legacy_map:
        return {"oracle": OracleAgent, "naive": NaiveAgent, "adaptive": AdaptiveAgent}[name]()
    if name == "oracle":
        return LOracle()
    if name == "naive":
        return LNaive()
    if p.type_name == "identity":
        return LAdaptive("?")  # no change to find: stays on the documented map unless it sees a miss
    if p.reference_level is None:
        raise ValueError(f"no ideal estimator for rule type {p.type_name}; use family_estimator or adaptive_library")
    return LAdaptive(p.reference_level)


def supports(name: str, perturbation: Perturbation) -> bool:
    try:
        make_reference(name, perturbation)
    except (ValueError, KeyError):
        return False
    return True


__all__ = [
    "DEFAULT_REFERENCES",
    "REFERENCE_NAMES",
    "AdaptiveAgent",
    "AdaptiveLibrary",
    "CamAdaptive",
    "CamNaive",
    "CamOracle",
    "FamilyEstimator",
    "LAdaptive",
    "LNaive",
    "LOracle",
    "LocalBroyden",
    "LocalPatcher",
    "NaiveAgent",
    "NumericAgent",
    "OracleAgent",
    "make_reference",
    "supports",
]
