"""G4_faq_1to1 — FAQ HTML phải khớp 1:1 acceptedAnswer trong JSON-LD FAQPage.

Phụ thuộc JSON-LD trong context: ctx.jsonld is None ⇒ status="blocked" (schema-dependent).
HTML FAQ heuristic: cặp (heading h2..h4 / <summary> / <dt>) + phần trả lời liền sau
(<p>/<dd>/nội dung <details>).
"""
from __future__ import annotations

import json
import re

from app.gates.base import GateResult, Violation, gate
from app.gates.html_utils import clean_ckeditor_spans, parse

_WS = re.compile(r"\s+")


def _norm(s: str) -> str:
    return _WS.sub(" ", (s or "").strip()).lower()


def _find_faqpage(jsonld):
    """Trả về node FAQPage đầu tiên (hỗ trợ @graph / list / dict đơn)."""
    if isinstance(jsonld, dict):
        if "@graph" in jsonld:
            return _find_faqpage(jsonld["@graph"])
        t = jsonld.get("@type")
        types = t if isinstance(t, list) else [t]
        if "FAQPage" in types:
            return jsonld
        return None
    if isinstance(jsonld, list):
        for node in jsonld:
            found = _find_faqpage(node)
            if found:
                return found
    return None


def _jsonld_faqs(jsonld) -> list[tuple[str, str]]:
    page = _find_faqpage(jsonld)
    if not page:
        return []
    main = page.get("mainEntity") or []
    if isinstance(main, dict):
        main = [main]
    out: list[tuple[str, str]] = []
    for q in main:
        if not isinstance(q, dict):
            continue
        name = q.get("name", "")
        ans = q.get("acceptedAnswer") or {}
        if isinstance(ans, list):
            ans = ans[0] if ans else {}
        text = ans.get("text", "") if isinstance(ans, dict) else ""
        out.append((_norm(name), _norm(text)))
    return out


def _html_faqs(body_html: str) -> list[tuple[str, str]]:
    soup = parse(clean_ckeditor_spans(body_html))
    out: list[tuple[str, str]] = []
    # heading Q + đoạn trả lời liền sau
    for h in soup.find_all(["h2", "h3", "h4", "summary", "dt"]):
        q = h.get_text(" ")
        ans_el = h.find_next_sibling(["p", "dd", "div"])
        a = ans_el.get_text(" ") if ans_el else ""
        out.append((_norm(q), _norm(a)))
    return out


@gate("G4_faq_1to1")
def check(ctx: dict) -> GateResult:
    jsonld = ctx.get("jsonld")
    if jsonld is None:
        return GateResult("G4_faq_1to1", "blocked",
                          [Violation("jsonld", "không có JSON-LD trong context (schema-dependent)")])
    if isinstance(jsonld, str):
        try:
            jsonld = json.loads(jsonld)
        except json.JSONDecodeError:
            return GateResult("G4_faq_1to1", "blocked",
                              [Violation("jsonld", "JSON-LD không parse được")])

    j = _jsonld_faqs(jsonld)
    h = _html_faqs(ctx.get("body_html", ""))
    vios: list[Violation] = []

    if len(h) != len(j):
        vios.append(Violation(
            locator="faq.count",
            evidence=f"số FAQ HTML ({len(h)}) khác acceptedAnswer JSON-LD ({len(j)})",
        ))

    j_map = dict(j)
    for i, (q, a) in enumerate(h):
        if q not in j_map:
            vios.append(Violation(f"faq[{i}]", f'câu hỏi HTML không có trong JSON-LD: "{q}"'))
        elif j_map[q] != a:
            vios.append(Violation(f"faq[{i}]", f'answer lệch cho câu hỏi: "{q}"'))

    return GateResult("G4_faq_1to1", "fail" if vios else "pass", vios)
