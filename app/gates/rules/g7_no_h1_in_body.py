"""G7_no_h1_in_body — body KHÔNG được chèn <h1> (H1 nằm trong template CMS)."""
from __future__ import annotations

from app.gates.base import GateResult, Violation, gate
from app.gates.html_utils import parse


@gate("G7_no_h1_in_body")
def check(ctx: dict) -> GateResult:
    soup = parse(ctx.get("body_html", ""))
    vios = [
        Violation(locator=f"h1[{i}]", evidence=h.get_text()[:80])
        for i, h in enumerate(soup.find_all("h1"))
    ]
    return GateResult("G7_no_h1_in_body", "fail" if vios else "pass", vios)
