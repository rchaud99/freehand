"""Registry of perturbation types.

A suite names its perturbations and gives each a type and typed parameters:

    perturbations:
      rot13:   {type: L2_rotation, params: {degrees: 13}}
      L3shear: {type: L3_affine, params: {sx: 1.12, sy: 0.90, shear_deg: 7.0}}

`build(name, spec, seed)` validates the parameters against the type's dataclass and returns a fresh instance (fresh,
because stateful rules carry per-episode state). To add a rule: subclass `Perturbation` (see base.py), give it a
`type_name` and a frozen `Params` dataclass, and add it to `_TYPES` below. See docs/perturbations.md.
"""

from __future__ import annotations

from typing import Any

from freehand.perturbations.base import NoParams, Params, Perturbation
from freehand.perturbations.calibration import (
    LADDER_KNOBS,
    LADDER_TYPES,
    L2Rotation,
    L3Affine,
    L4Backlash,
    L5Drift,
    L6Attribution,
    L7Scarce,
    OffsetChange,
    PlotterMapChange,
    RotationChange,
    ScaleChange,
    ladder_params,
)
from freehand.perturbations.camera import CameraMove
from freehand.perturbations.discriminating import CommandDynamics, CrossAxisWarp, LatentMirror
from freehand.sim.plotter import PlotterMap

_TYPES: dict[str, type[Perturbation]] = {
    cls.type_name: cls
    for cls in (
        Perturbation,  # identity
        PlotterMapChange,  # none
        OffsetChange,
        RotationChange,
        ScaleChange,
        L2Rotation,
        L3Affine,
        L4Backlash,
        L5Drift,
        L6Attribution,
        L7Scarce,
        CommandDynamics,
        LatentMirror,
        CrossAxisWarp,
        CameraMove,
    )
}

TIERS = {
    "control": ["identity", "none"],
    "calibration": [
        "offset",
        "rotation",
        "scale",
        "L2_rotation",
        "L3_affine",
        "L4_backlash",
        "L5_drift",
        "L6_attribution",
        "L7_scarce",
    ],
    "discriminating": ["command_memory", "latent_mirror", "smooth_warp"],
    "camera": ["camera_move"],
}


def types() -> dict[str, type[Perturbation]]:
    return dict(_TYPES)


def get_type(type_name: str) -> type[Perturbation]:
    try:
        return _TYPES[type_name]
    except KeyError:
        raise KeyError(f"unknown perturbation type {type_name!r}; known: {sorted(_TYPES)}") from None


def build(name: str, spec: dict[str, Any], seed: int) -> Perturbation:
    """A fresh perturbation instance for one episode. spec: {type, params?, step?}."""
    if "type" not in spec:
        raise ValueError(f"perturbation {name!r}: missing `type`")
    unknown = set(spec) - {"type", "params", "step"}
    if unknown:
        raise ValueError(f"perturbation {name!r}: unknown keys {sorted(unknown)}")
    cls = get_type(spec["type"])
    params = cls.params_cls.from_dict(spec.get("params"))
    step = int(spec.get("step", 1)) - 1
    return cls(seed, params, name=name, step=step)


def validate_spec(name: str, spec: dict[str, Any]) -> None:
    """Raise if the spec's type or parameters are invalid (without building: no seed needed)."""
    if "type" not in spec:
        raise ValueError(f"perturbation {name!r}: missing `type`")
    get_type(spec["type"]).params_cls.from_dict(spec.get("params"))


# ---------------------------------------------------------------- reconstruction of historical episodes
_LEVEL_TYPES = {
    "L2rot": "L2_rotation",
    "L3": "L3_affine",
    "L4": "L4_backlash",
    "L5": "L5_drift",
    "L6": "L6_attribution",
    "L7": "L7_scarce",
    "X_ARX": "command_memory",
    "X_MODE": "latent_mirror",
    "X_WARP": "smooth_warp",
    "?": "identity",
}
_CAMERA_CONDS = {"cam_transfer": "transfer", "cam_fresh": "fresh", "cam_static": "static"}


def _params_from_knob(level: str, knob, variant: str) -> dict:
    if level == "L2rot":
        return {"degrees": 13.0}
    if level == "L3":
        return {"sx": knob[0], "sy": knob[1], "shear_deg": knob[2]}
    if level == "L4":
        return {"play_mm": knob}
    if level == "L5":
        return {"mm_per_stroke": knob[0], "skip_prob": knob[1]}
    if level == "L6":
        return {"camera_shift_mm": knob[0], "camera_rot_deg": knob[1], "plotter_offset_mm": knob[2], "variant": variant}
    if level == "L7":
        return {"tol_mm": knob}
    if level == "X_ARX":
        return {"gains": list(knob)}
    if level == "X_MODE":
        return {"threshold_mm": knob}
    if level == "X_WARP":
        return {"amplitude_mm": knob}
    return {}


def from_describe(desc: dict, seed: int) -> Perturbation:
    """Rebuild a rule from its describe() dict (new summaries and converted legacy episodes)."""
    name = str(desc.get("name") or desc.get("type"))
    if desc.get("type") in ("none", "offset", "rotation", "scale") and "map_after" in desc:
        p = PlotterMapChange(seed, NoParams(), name=name)
        p.map = PlotterMap(**desc["map_after"])  # exactly the logged map
        return p
    return build(name, {"type": desc["type"], "params": desc.get("params") or {}, "step": desc.get("step", 1)}, seed)


def from_legacy_episode(ep: dict) -> Perturbation:
    """Rebuild the rule of a historical episode.json (scenario describe dict, camera condition or plotter map)."""
    seed = ep["seed"]
    d = ep.get("scenario")
    if d:
        level = d["level"]
        spec = {
            "type": _LEVEL_TYPES[level],
            "params": _params_from_knob(level, d.get("knob"), d.get("variant", "")),
            "step": d.get("step", 1),
        }
        return build(ep.get("pert", _LEVEL_TYPES[level]), spec, seed)
    cond = ep.get("pert", "none")
    if cond in _CAMERA_CONDS:
        return build(cond, {"type": "camera_move", "params": {"mode": _CAMERA_CONDS[cond]}}, seed)
    m = PlotterMap(**ep.get("map_after", {}))
    p = PlotterMapChange(seed, NoParams(), name=cond)
    p.map = m  # exactly the logged map (no redraw)
    return p


__all__ = [
    "LADDER_KNOBS",
    "LADDER_TYPES",
    "TIERS",
    "CameraMove",
    "CommandDynamics",
    "CrossAxisWarp",
    "L2Rotation",
    "L3Affine",
    "L4Backlash",
    "L5Drift",
    "L6Attribution",
    "L7Scarce",
    "LatentMirror",
    "NoParams",
    "OffsetChange",
    "Params",
    "Perturbation",
    "PlotterMapChange",
    "RotationChange",
    "ScaleChange",
    "build",
    "from_describe",
    "from_legacy_episode",
    "get_type",
    "ladder_params",
    "types",
    "validate_spec",
]
