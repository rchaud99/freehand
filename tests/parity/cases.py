"""The 150 legacy-parity cases (shared by the recorder and the test). Ids are stable: the fixture is keyed on them."""
from __future__ import annotations

CASES: list[dict] = []
DEFAULTS = {"seed": 7, "n": 6, "P": 3, "legacy": "b", "agent": "fake", "memory": True, "disclosure": "silent",
            "k_prev": 2, "show_history": True, "history_landed": False, "block": "", "output_mode": "mm",
            "feedback": "image", "page": "default", "cost_cap": None}


def add(**kw) -> None:
    case = {**DEFAULTS, **kw}
    case["id"] = f"c{len(CASES):02d}_" + kw["id"]
    CASES.append(case)


# plotter-map conditions, reference agents
for cond in ("none", "offset10", "rot13", "scale73", "offset5", "rot6", "scale95", "rot3"):
    for ag in ("oracle", "naive", "adaptive"):
        add(id=f"map_{cond}_{ag}", cond=cond, agent=ag, seed=10 if cond in ("rot13", "scale73") else 7, n=8, P=4)
# camera conditions, reference agents
for cond in ("cam_transfer", "cam_fresh", "cam_static"):
    for ag in ("oracle", "naive", "adaptive"):
        add(id=f"{cond}_{ag}", cond=cond, agent=ag, n=8, P=4)
# ladder levels, every rung, level references
for level, variants in (("L3", [""]), ("L4", [""]), ("L5", [""]), ("L6", ["cam", "plot", "both"]), ("L7", [""])):
    for step in range(3):
        for v in variants:
            for ag in ("oracle", "naive", "adaptive"):
                add(id=f"{level}{v}_k{step + 1}_{ag}", scenario={"level": level, "step": step, "variant": v},
                    agent=ag, seed=10, n=8, P=4)
for ag in ("oracle", "naive", "adaptive"):
    add(id=f"L2rot_{ag}", scenario={"level": "L2rot"}, agent=ag, seed=10, n=8, P=4)
    add(id=f"objpage_rot13_{ag}", scenario={"level": "L2rot"}, agent=ag, seed=10, n=20, P=4, page="objective")
# discriminating rules (Codex copy), publication page, reference agents incl. the numeric ones
for fam in ("arx", "mode", "warp", "identity"):
    agents = ("oracle", "naive", "local_patcher", "local_broyden", "adaptive_library")
    for ag in agents + (("family_estimator",) if fam != "identity" else ()):
        add(id=f"X_{fam}_{ag}", x=fam, agent=ag, seed=2001, n=12, P=3, legacy="a", page="publication")
add(id="X_arx_P0_oracle", x="arx", agent="oracle", seed=2001, n=2, P=0, legacy="a", page="publication")
# a scripted fake model through every arm variant
for cond in ("offset10", "none"):
    for disc in ("silent", "alerted", "scaffolded"):
        add(id=f"fake_{cond}_{disc}", cond=cond, disclosure=disc, n=8, P=4)
add(id="fake_cam_transfer", cond="cam_transfer", n=6, P=3)
add(id="fake_cam_fresh", cond="cam_fresh", n=6, P=3)
add(id="fake_cam_alerted", cond="cam_transfer", disclosure="scaffolded", n=6, P=3)
add(id="fake_nomem", cond="offset10", memory=False)
add(id="fake_nohist", cond="offset10", show_history=False)
add(id="fake_k0", cond="offset10", k_prev=0)
add(id="fake_crop", cond="scale73", output_mode="crop_px", seed=10)
add(id="fake_crop_nomem", cond="scale73", output_mode="crop_px", memory=False, seed=10)
OBJ = {"seed": 10, "n": 20, "P": 4, "page": "objective"}
add(id="fake_obj_rot13_objective", scenario={"level": "L2rot"}, block="objective", **OBJ)
add(id="fake_obj_L3_informed", scenario={"level": "L3", "step": 1, "variant": ""}, block="informed", **OBJ)
add(id="fake_obj_L6cam_informed", scenario={"level": "L6", "step": 0, "variant": "cam"}, block="informed", **OBJ)
add(id="fake_obj_L6cam_crop", scenario={"level": "L6", "step": 0, "variant": "cam"}, block="informed",
    output_mode="crop_px", **OBJ)
add(id="fake_stateless_image", scenario={"level": "L2rot"}, block="informed", memory=False, **OBJ)
add(id="fake_stateless_numeric", scenario={"level": "L2rot"}, block="informed", memory=False, history_landed=True,
    **OBJ)
add(id="fake_L7", scenario={"level": "L7", "step": 2, "variant": ""}, seed=10, n=8, P=4)
PUB = {"seed": 4001, "n": 12, "P": 3, "legacy": "a", "page": "publication", "feedback": "image_numeric",
       "block": "model_study"}
add(id="fake_numeric_feedback", x="arx", **PUB)
add(id="fake_numeric_feedback_alerted", x="mode", disclosure="alerted", **PUB)
add(id="fake_costcap", cond="offset10", cost_cap=0.02)
