"""G8_eeat — E-E-A-T structural: bài phải có tác giả thật + nguồn dẫn + ngày cập nhật.

Đọc ctx.meta (do n8n/CMS cấp):
  - author       : non-empty
  - updated_date : non-empty
  - nguồn dẫn    : meta.sources / meta.references non-empty, HOẶC ≥1 link http(s) trong body
Thiếu bất kỳ ⇒ violation tương ứng ⇒ fail.

INFERENCE (nới ở giai đoạn đầu): "≥1 <a> external tính là source" KHÔNG phân biệt link
uy tín (TDS/nguồn chính thống) với social/CTA/affiliate. Đây là kiểm lỏng để không chặn
oan bài có dẫn nguồn hợp lệ. Increment sau cần siết: allow-list domain nguồn, loại trừ
rel=nofollow/sponsored, tách CTA khỏi citation.
"""
from __future__ import annotations

from app.gates.base import GateResult, Violation, gate
from app.gates.html_utils import clean_ckeditor_spans, parse


def _has_external_link(body_html: str) -> bool:
    soup = parse(clean_ckeditor_spans(body_html))
    for a in soup.find_all("a", href=True):
        if str(a["href"]).strip().lower().startswith(("http://", "https://")):
            return True
    return False


def _nonempty(v) -> bool:
    if v is None:
        return False
    if isinstance(v, str):
        return bool(v.strip())
    if isinstance(v, (list, tuple, dict)):
        return len(v) > 0
    return True


@gate("G8_eeat")
def check(ctx: dict) -> GateResult:
    meta = ctx.get("meta") or {}
    vios: list[Violation] = []

    if not _nonempty(meta.get("author")):
        vios.append(Violation("meta.author", "thiếu tác giả thật"))
    if not _nonempty(meta.get("updated_date")):
        vios.append(Violation("meta.updated_date", "thiếu ngày cập nhật"))

    has_source = _nonempty(meta.get("sources")) or _nonempty(meta.get("references"))
    if not has_source and not _has_external_link(ctx.get("body_html", "")):
        vios.append(Violation("meta.sources", "thiếu nguồn dẫn (sources/references hoặc link ngoài)"))

    return GateResult("G8_eeat", "fail" if vios else "pass", vios)
