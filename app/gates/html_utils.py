"""Tiện ích HTML. Dọn span lồng nhau do CKEditor sinh TRƯỚC khi eval (không tính vi phạm)."""
from __future__ import annotations

from bs4 import BeautifulSoup


def parse(body_html: str) -> BeautifulSoup:
    return BeautifulSoup(body_html or "", "html.parser")


def clean_ckeditor_spans(body_html: str) -> str:
    """Unwrap span rác CKEditor: chỉ gỡ khi KHÔNG style AND KHÔNG class AND KHÔNG
    có attr `data-*`. Giữ span mang data-* (vd data-claim-id) để G2 nhận diện nguồn
    claim khi dùng chung pipeline clean với các gate khác.
    """
    soup = parse(body_html)
    for span in soup.find_all("span"):
        has_data_attr = any(str(k).startswith("data-") for k in span.attrs)
        if not span.get("style") and not span.get("class") and not has_data_attr:
            span.unwrap()
    return str(soup)
