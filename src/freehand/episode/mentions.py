"""Keyword screens over notes, memory and reasoning.

These are UNVALIDATED search aids (see docs/findings.md): words such as "landed" or "compensate" do not establish a
causal belief about the plotter, and a camera attribution needs a behavioural probe or adjudicated annotation. They
are kept because the historical metrics used them, and they are reported as `keyword_screen` fields.
"""
from __future__ import annotations

import re

MENTION_B = re.compile(
    r"\b(offset\w*|shift\w*|displac\w*|misalign\w*|drift\w*|calibrat\w*|rotat\w*|skew\w*|compensat\w*|"
    r"systematic\w*|(?:is|are|been|being|was|were) scaled|scale factor|shrunk|shrink\w*|not where|off[- ]target|"
    r"landed (?:\w+ ){0,4}(?:off|away|left|right|above|below|short|high|low|up|down)|"
    r"lands? (?:\w+ ){0,4}(?:off|away|left|right|above|below|short|high|low|up|down)|"
    r"plotter (?:is|seems|has|may|might)|has changed|changed)\b", re.I)
MENTION_A = re.compile(
    r"\b(camera|viewpoint|view (?:has |was )?(?:changed|moved|shifted|rotated)|angle|perspective|tilt\w*|rotat\w*|"
    r"moved|homograph\w*|mapping|re-?anchor\w*|skew\w*|warp\w*|has changed|changed)\b", re.I)

# Attribution screen of the ladder: camera vs plotter wording.
CAM_RX = re.compile(
    r"(camera|viewpoint|view (?:has |was |is )?(?:moved|shifted|changed|rotated)|image (?:has |was |is )?"
    r"(?:moved|shifted|rotated)|photo (?:has |was )?(?:moved|shifted)|(?:old|earlier|previous|existing|"
    r"prior|closed) (?:marks|strokes|ink|squares|lines)[^.;]{0,60}(?:moved|shifted|displaced|appear)|"
    r"everything (?:has )?(?:moved|shifted)|whole (?:page|image|drawing)|page (?:has |was |is )?"
    r"(?:moved|shifted|rotated)|re-?anchor|rectification|calibration of the (?:view|camera))", re.I)
PLOT_RX = re.compile(
    r"(plotter|pen (?:is |now )?(?:landing|drifting|offset)|(?:ink|strokes?|marks?) (?:now )?"
    r"(?:lands?|landed|landing)|landed|lands (?:about|roughly)|compensat\w*|backlash|drift\w*|skipp\w*|"
    r"direction[- ]dependent)", re.I)


def mention_regex(family: str) -> re.Pattern:
    return MENTION_A if family == "camera" else MENTION_B


def attribution(turns: list[dict], perturb_after: int) -> tuple[str, int | None, str]:
    """First post-change turn whose note or memory mentions a cause: (camera|plotter|both|none, turn index, text).
    Works on historical turn records and on new ones (both carry `square` and the parsed `action`)."""
    post = [t for t in turns if t["square"] > perturb_after]
    for i, t in enumerate(post):
        a = t.get("action") or {}
        txt = f"{a.get('note', '')} || {a.get('memory', '')}"
        cam, plo = bool(CAM_RX.search(txt)), bool(PLOT_RX.search(txt))
        if cam or plo:
            return ("both" if cam and plo else ("camera" if cam else "plotter")), i + 1, txt[:400]
    return "none", None, ""
