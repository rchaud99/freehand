"""Arms: what an LLM agent is told and what it remembers.

An arm composes
  memory mode      memory=True: one running conversation (earlier replies with a reasoning summary, the previous
                   `k_prev` photos downscaled, and a ~150-word notepad echoed each turn); memory=False: stateless,
                   every turn is one fresh request (system prompt, current photo, state block)
  history          the state block lists every commanded stroke (show_history), optionally with where its ink
                   landed as measured numbers (history_landed: the stateless-numeric arm)
  disclosure       silent | alerted | scaffolded (what the system prompt says about possible changes)
  prompt blocks    extra system-prompt paragraphs (objective, informed_objective, model_study ...: blocks/*.txt)
  feedback         image | image_numeric (the state block also carries NUMERIC_FEEDBACK_JSON: target + landed ends)
  output mode      None = the model's registry default; page_mm | crop_px to force one
The same arm is applied to every model; the output mode is the only per-model part.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Any

from freehand import prompts

DISCLOSURES = ("silent", "alerted", "scaffolded")
FEEDBACKS = ("image", "image_numeric")
MEMORY_WORDS = 150  # notepad size the prompt asks for
NOTEPAD_KEEP_WORDS = MEMORY_WORDS + 50  # the harness keeps this many words of the notepad
REASONING_CHARS = 400  # reasoning summary kept per earlier turn in the conversation
DEFAULT_K_PREV = 2


@dataclass(frozen=True)
class Arm:
    name: str
    memory: bool = True
    k_prev: int = DEFAULT_K_PREV
    show_history: bool = True
    history_landed: bool = False
    disclosure: str = "silent"
    blocks: tuple[str, ...] = ()
    feedback: str = "image"
    output_mode: str | None = None
    prompt_version: str = prompts.DEFAULT_VERSION

    def __post_init__(self):
        if self.disclosure not in DISCLOSURES:
            raise ValueError(f"arm {self.name}: disclosure must be one of {DISCLOSURES}")
        if self.feedback not in FEEDBACKS:
            raise ValueError(f"arm {self.name}: feedback must be one of {FEEDBACKS}")
        if self.disclosure == "scaffolded" and not self.memory:
            raise ValueError(f"arm {self.name}: scaffolded disclosure needs the memory notepad")
        if self.k_prev < 0:
            raise ValueError(f"arm {self.name}: k_prev must be >= 0")
        known = prompts.block_ids(self.prompt_version)
        for b in self.blocks:
            if b not in known:
                raise ValueError(f"arm {self.name}: unknown prompt block {b!r}; known: {known}")
        if self.output_mode is not None:
            from freehand.llm.registry import normalize_output_mode

            object.__setattr__(self, "output_mode", normalize_output_mode(self.output_mode))

    def block_text(self) -> str:
        return "\n\n".join(prompts.text(f"{self.prompt_version}/blocks/{b}") for b in self.blocks)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["blocks"] = list(self.blocks)
        return d


# Named presets. The historical arm names are kept so old and new results line up.
PRESETS: dict[str, Arm] = {
    a.name: a
    for a in (
        Arm("silent"),
        Arm("alerted", disclosure="alerted"),
        Arm("scaffolded", disclosure="scaffolded"),
        Arm("nomemory", memory=False),
        Arm("nohistory", show_history=False),
        Arm("objective", blocks=("objective",)),
        Arm("informed_objective", blocks=("informed_objective",)),
        Arm("stateless_image", memory=False, blocks=("informed_objective",)),
        Arm("stateless_numeric", memory=False, history_landed=True, blocks=("informed_objective",)),
        Arm("study_image", blocks=("model_study",)),
        Arm("study_image_numeric", blocks=("model_study",), feedback="image_numeric"),
    )
}
CODE_ARM = Arm("code", memory=False)  # the arm label of reference agents (they read no prompt)


def get_arm(name: str) -> Arm:
    try:
        return PRESETS[name]
    except KeyError:
        raise KeyError(
            f"unknown arm {name!r}; presets: {sorted(PRESETS)} (or define it inline in the experiment config)"
        ) from None


def arm_from_config(name: str, cfg: dict[str, Any] | None) -> Arm:
    """An arm from an experiment config entry: {preset: <name>, ...overrides} or a full definition."""
    cfg = dict(cfg or {})
    base = get_arm(cfg.pop("preset")) if "preset" in cfg else Arm(name)
    if "blocks" in cfg:
        cfg["blocks"] = tuple(cfg["blocks"])
    allowed = {f for f in Arm.__dataclass_fields__ if f != "name"}
    unknown = set(cfg) - allowed
    if unknown:
        raise ValueError(f"arm {name}: unknown field(s) {sorted(unknown)}; allowed: {sorted(allowed)}")
    return replace(base, name=name, **cfg)
