"""G2_claim_provenance — DETECTOR (Blocker #2: SSOT giá/TDS/bảo hành chưa có).

Đếm numeric claim (giá / % / thông số / năm bảo hành) KHÔNG kèm claim_id trỏ về SSOT.
Vì `claims` chưa được nhập+khoá version, gate chạy dạng report-only:
  - có claim thiếu id  -> status="blocked" (cần người gắn nguồn), KHÔNG BAO GIỜ "fail"
  - không có claim / mọi claim đã có id -> "pass"
Khi Blocker #2 đóng sẽ nâng thành "fail". Dùng chung pipeline clean_ckeditor_spans như
các gate khác — clean nay giữ span mang `data-*` nên marker `data-claim-id` không bị gỡ.
"""
from __future__ import annotations

import re

from app.gates.base import GateResult, Violation, gate
from app.gates.html_utils import clean_ckeditor_spans, parse

# Mỗi pattern = một loại numeric claim cần nguồn.
_CLAIM_PATTERNS = [
    re.compile(r"\d[\d.,]*\s*(?:đ|vnđ|vnd|đồng|triệu)\b", re.IGNORECASE),   # giá
    re.compile(r"\d+(?:[.,]\d+)?\s*%"),                                      # phần trăm
    re.compile(r"\d+(?:[.,]\d+)?\s*(?:nm|°c|°|lớp|w|kw)\b", re.IGNORECASE),  # thông số
    re.compile(r"\d+\s*năm\b", re.IGNORECASE),                              # bảo hành (năm)
]

CLAIM_ATTR = "data-claim-id"


def _has_claim_ancestor(node) -> bool:
    cur = node.parent
    while cur is not None:
        get = getattr(cur, "get", None)
        if get and cur.get(CLAIM_ATTR):
            return True
        cur = cur.parent
    return False


@gate("G2_claim_provenance")
def check(ctx: dict) -> GateResult:
    soup = parse(clean_ckeditor_spans(ctx.get("body_html", "")))  # clean giữ span data-*
    vios: list[Violation] = []
    for text_node in soup.find_all(string=True):
        s = str(text_node)
        if _has_claim_ancestor(text_node):
            continue
        for pat in _CLAIM_PATTERNS:
            for m in pat.finditer(s):
                vios.append(Violation(
                    locator="body",
                    evidence=f'numeric claim thiếu claim_id → SSOT: "{m.group(0).strip()}"',
                ))
    # DETECTOR: có vi phạm ⇒ blocked (cần người), không tính fail.
    status = "blocked" if vios else "pass"
    return GateResult("G2_claim_provenance", status, vios)
