"""G9_no_raw_script — cấm <script> raw trong body. Bắt AdSense ca-pub-1256170089840912."""
from __future__ import annotations

from app.gates.base import GateResult, Violation, gate
from app.gates.html_utils import parse

ADSENSE_PUB = "ca-pub-1256170089840912"


@gate("G9_no_raw_script")
def check(ctx: dict) -> GateResult:
    soup = parse(ctx.get("body_html", ""))
    vios: list[Violation] = []
    for i, s in enumerate(soup.find_all("script")):
        src = s.get("src", "") or s.get_text()[:80]
        tag = "adsense" if ADSENSE_PUB in str(s) else "script"
        vios.append(Violation(locator=f"script[{i}]", evidence=f"{tag}: {src}".strip()))
    return GateResult("G9_no_raw_script", "fail" if vios else "pass", vios)
