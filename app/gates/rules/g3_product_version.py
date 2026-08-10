"""G3_product_version — heuristic/warn (is_blocking=False).

Phát hiện trộn năm sản phẩm (vd 2023 và 2026) trong cùng một scope gần nhau
(cùng <td>/<li>/<p>/heading, hoặc cùng câu nếu không có block). FP cao ⇒ đăng ký
advisory: vẫn trả status="fail" khi có trộn (fact) nhưng gate.is_blocking=False nên
consumer chỉ surface warning, không chặn request-approval.
"""
from __future__ import annotations

import re

from app.gates.base import GateResult, Violation, gate
from app.gates.html_utils import clean_ckeditor_spans, parse

_YEAR = re.compile(r"\b(202[0-7])\b")           # năm sản phẩm 2020..2027
_BLOCKS = ["td", "th", "li", "p", "caption", "h1", "h2", "h3", "h4", "h5", "h6", "div"]
_SENT_SPLIT = re.compile(r"[.!?;\n]+")


def _years(text: str) -> set[str]:
    return set(_YEAR.findall(text))


@gate("G3_product_version", blocking=False)
def check(ctx: dict) -> GateResult:
    soup = parse(clean_ckeditor_spans(ctx.get("body_html", "")))
    vios: list[Violation] = []

    blocks = soup.find_all(_BLOCKS)
    if blocks:
        for i, b in enumerate(blocks):
            ys = _years(b.get_text(" "))
            if len(ys) >= 2:
                vios.append(Violation(
                    locator=f"{b.name}[{i}]",
                    evidence=f"trộn năm sản phẩm: {sorted(ys)} trong cùng khối",
                ))
    else:
        text = soup.get_text(" ")
        for j, sent in enumerate(_SENT_SPLIT.split(text)):
            ys = _years(sent)
            if len(ys) >= 2:
                vios.append(Violation(
                    locator=f"sentence[{j}]",
                    evidence=f"trộn năm sản phẩm: {sorted(ys)} trong cùng câu",
                ))
    return GateResult("G3_product_version", "fail" if vios else "pass", vios)
