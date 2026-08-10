"""G1_superlatives — cấm cụm từ tuyệt đối/so-sánh-nhất trong body (linguistic).

Danh sách khởi tạo theo CLAUDE.md §6, có thể mở rộng. So khớp trên text đã strip HTML,
fold dấu (diacritic-insensitive) nên "tối ưu hoá" và "tối ưu hóa" gộp một pattern.
"""
from __future__ import annotations

import re
import unicodedata

from app.gates.base import GateResult, Violation, gate
from app.gates.html_utils import clean_ckeditor_spans, parse

# PROVISIONAL — danh sách cần validate/tune bằng FP trên corpus stg_news_items
# (điều kiện thoát Phase 2). Các entry có nguy cơ FP đã biết: "duy nhất" (cách duy
# nhất/con duy nhất), "hàng đầu" (hàng đầu tiên). KHÔNG hand-tune trên ví dụ tự nghĩ
# — chờ đo corpus. "số 1"/"số một" bare đã bỏ (số thứ tự gây FP: "cửa số 1"); thay bằng
# cụm neo superlative không mơ hồ.
# Cụm từ cấm (dạng gốc, người-đọc). Fold về ascii-lower khi so khớp.
BANNED_PHRASES = [
    "toàn diện nhất",
    "tối ưu hoá",      # gộp cả "tối ưu hóa" sau khi fold dấu
    "duy nhất",
    "tốt nhất",
    "hàng đầu",
    "đỉnh cao",
    "hoàn hảo",
    "vượt trội",
    # cụm neo "số 1" — chỉ khi đi kèm ngữ cảnh xếp hạng/thị trường (tránh số thứ tự)
    "đứng số 1",
    "xếp số 1",
    "thương hiệu số 1",
    "đơn vị số 1",
    "sản phẩm số 1",
    "số 1 thị trường",
    "số 1 việt nam",
    "số 1 về",
]


def _fold(s: str) -> str:
    """Lowercase + bỏ dấu tiếng Việt (NFD, gỡ combining mark) + đ→d."""
    s = s.replace("đ", "d").replace("Đ", "D")
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.lower()


# Precompile: mỗi phrase -> regex có word-boundary để tránh "số 1" khớp trong "số 10".
_PATTERNS = [
    (p, re.compile(r"\b" + re.escape(_fold(p)) + r"\b"))
    for p in BANNED_PHRASES
]


@gate("G1_superlatives")
def check(ctx: dict) -> GateResult:
    text = parse(clean_ckeditor_spans(ctx.get("body_html", ""))).get_text(" ")
    folded = _fold(text)
    vios: list[Violation] = []
    for original, pat in _PATTERNS:
        for _ in pat.finditer(folded):
            vios.append(Violation(locator="body", evidence=f'cụm từ cấm: "{original}"'))
    return GateResult("G1_superlatives", "fail" if vios else "pass", vios)
