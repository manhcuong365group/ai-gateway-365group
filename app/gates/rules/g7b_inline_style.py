"""G7b_inline_style — warn (is_blocking=False). CMS lột `class` nên phải dùng inline style.

Sau khi dọn span rác CKEditor, mọi thẻ nội dung còn mang `class=` là rủi ro mất style
khi CMS render. Đăng ký advisory: có `class` ⇒ status="fail" (fact) nhưng không chặn.
"""
from __future__ import annotations

from app.gates.base import GateResult, Violation, gate
from app.gates.html_utils import clean_ckeditor_spans, parse


@gate("G7b_inline_style", blocking=False)
def check(ctx: dict) -> GateResult:
    soup = parse(clean_ckeditor_spans(ctx.get("body_html", "")))
    vios: list[Violation] = []
    for i, el in enumerate(soup.find_all(class_=True)):
        cls = " ".join(el.get("class", []))
        vios.append(Violation(
            locator=f"{el.name}[{i}]",
            evidence=f'dùng class="{cls}" (CMS lột class — chuyển sang inline style)',
        ))
    return GateResult("G7b_inline_style", "fail" if vios else "pass", vios)
