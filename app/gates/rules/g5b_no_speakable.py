"""G5b_no_speakable — cấm 'speakable' trong JSON-LD (không hỗ trợ nội dung tiếng Việt)."""
from __future__ import annotations

import json

from app.gates.base import GateResult, Violation, gate


def _has_speakable(node) -> bool:
    if isinstance(node, dict):
        if any(str(k).lower() == "speakable" for k in node):
            return True
        return any(_has_speakable(v) for v in node.values())
    if isinstance(node, list):
        return any(_has_speakable(v) for v in node)
    return False


@gate("G5b_no_speakable")
def check(ctx: dict) -> GateResult:
    jsonld = ctx.get("jsonld")
    if jsonld is None:
        return GateResult("G5b_no_speakable", "blocked",
                          [Violation("jsonld", "không có JSON-LD trong context (Blocker nguồn schema)")])
    if isinstance(jsonld, str):
        try:
            jsonld = json.loads(jsonld)
        except json.JSONDecodeError:
            return GateResult("G5b_no_speakable", "blocked",
                              [Violation("jsonld", "JSON-LD không parse được")])
    if _has_speakable(jsonld):
        return GateResult("G5b_no_speakable", "fail",
                          [Violation("jsonld.speakable", "có thuộc tính speakable — phải gỡ")])
    return GateResult("G5b_no_speakable", "pass", [])
