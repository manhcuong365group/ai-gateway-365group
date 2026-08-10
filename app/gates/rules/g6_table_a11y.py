"""G6_table_a11y — mọi <table> phải có <thead> và ít nhất một <th scope="col">."""
from __future__ import annotations

from app.gates.base import GateResult, Violation, gate
from app.gates.html_utils import parse


@gate("G6_table_a11y")
def check(ctx: dict) -> GateResult:
    soup = parse(ctx.get("body_html", ""))
    vios: list[Violation] = []
    for i, t in enumerate(soup.find_all("table")):
        problems = []
        if not t.find("thead"):
            problems.append("thiếu <thead>")
        if not t.find("th", attrs={"scope": "col"}):
            problems.append('thiếu th scope="col"')
        if problems:
            vios.append(Violation(locator=f"table[{i}]", evidence="; ".join(problems)))
    return GateResult("G6_table_a11y", "fail" if vios else "pass", vios)
