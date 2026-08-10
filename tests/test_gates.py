"""TDD gate engine — mỗi rule có bad-case (fail) + good-case (pass).
Pattern này để nhân rộng cho G1–G9 còn lại và đo false-positive trên corpus stg_news_items.
"""
import pytest

from app.gates import run_all
from app.gates.base import REGISTRY
from app.gates.html_utils import clean_ckeditor_spans


def _run(rule_id, ctx):
    return REGISTRY[rule_id].fn(ctx)


# ---------- G9_no_raw_script ----------
def test_g9_fail_adsense():
    html = '<p>bài</p><script src="https://pagead2.../ca-pub-1256170089840912"></script>'
    r = _run("G9_no_raw_script", {"body_html": html})
    assert r.status == "fail"
    assert "adsense" in r.violations[0].evidence

def test_g9_pass_clean():
    r = _run("G9_no_raw_script", {"body_html": "<p>nội dung sạch</p>"})
    assert r.status == "pass"


# ---------- G7_no_h1_in_body ----------
def test_g7_fail_h1():
    r = _run("G7_no_h1_in_body", {"body_html": "<h1>Tiêu đề</h1><p>x</p>"})
    assert r.status == "fail"

def test_g7_pass_h2():
    r = _run("G7_no_h1_in_body", {"body_html": "<h2>Mục</h2><p>x</p>"})
    assert r.status == "pass"


# ---------- G6_table_a11y ----------
def test_g6_fail_no_thead():
    r = _run("G6_table_a11y", {"body_html": "<table><tr><td>a</td></tr></table>"})
    assert r.status == "fail"

def test_g6_pass_proper_table():
    html = '<table><thead><tr><th scope="col">Mã</th></tr></thead><tbody><tr><td>CR BLK40</td></tr></tbody></table>'
    r = _run("G6_table_a11y", {"body_html": html})
    assert r.status == "pass"


# ---------- G5b_no_speakable ----------
def test_g5b_fail_speakable():
    ctx = {"jsonld": {"@type": "Article", "speakable": {"@type": "SpeakableSpecification"}}}
    r = _run("G5b_no_speakable", ctx)
    assert r.status == "fail"

def test_g5b_pass_clean():
    r = _run("G5b_no_speakable", {"jsonld": {"@type": "Article", "headline": "x"}})
    assert r.status == "pass"

def test_g5b_blocked_no_jsonld():
    r = _run("G5b_no_speakable", {"jsonld": None})
    assert r.status == "blocked"  # Blocker nguồn schema, không tính pass/fail


# ---------- CKEditor span cleanup ----------
def test_ckeditor_span_unwrap():
    dirty = "<p><span><span>text</span></span></p>"
    assert "<span>" not in clean_ckeditor_spans(dirty)

def test_ckeditor_span_keeps_data_attr():
    # span data-claim-id phải sống sót; span rác bên trong bị unwrap
    dirty = '<span data-claim-id="X"><span>1.200.000đ</span></span>'
    cleaned = clean_ckeditor_spans(dirty)
    assert 'data-claim-id="X"' in cleaned      # span ngoài giữ nguyên
    assert cleaned.count("<span") == 1          # span trong (rác) đã bị gỡ


# ---------- G1_superlatives (linguistic) ----------
def test_g1_fail_superlatives():
    html = "<p>Sản phẩm số 1, tốt nhất thị trường, phim toàn diện nhất</p>"
    r = _run("G1_superlatives", {"body_html": html})
    assert r.status == "fail"
    assert len(r.violations) >= 2

def test_g1_fail_diacritic_insensitive():
    # "tối ưu hóa" (dấu khác) vẫn phải bắt được
    r = _run("G1_superlatives", {"body_html": "<p>Giải pháp tối ưu hoá cho xe</p>"})
    assert r.status == "fail"

def test_g1_pass_clean():
    r = _run("G1_superlatives", {"body_html": "<p>Phim cách nhiệt hấp thụ hồng ngoại</p>"})
    assert r.status == "pass"

# "số 1" số thứ tự KHÔNG được fail; chỉ cụm neo superlative mới fail
def test_g1_pass_ordinal_door():
    r = _run("G1_superlatives", {"body_html": "<p>cửa số 1 bị kẹt</p>"})
    assert r.status == "pass"

def test_g1_pass_ordinal_step():
    r = _run("G1_superlatives", {"body_html": "<p>bước số 1: vệ sinh kính</p>"})
    assert r.status == "pass"

def test_g1_fail_rank_anchor():
    r = _run("G1_superlatives", {"body_html": "<p>đứng số 1 về doanh số</p>"})
    assert r.status == "fail"

def test_g1_fail_brand_anchor():
    r = _run("G1_superlatives", {"body_html": "<p>thương hiệu số 1 thị trường</p>"})
    assert r.status == "fail"


# ---------- G2_claim_provenance (DETECTOR — Blocker #2, không tính fail) ----------
def test_g2_blocked_numeric_without_claim_id():
    html = "<p>Giá chỉ 1.200.000đ, chặn 99% tia UV, bảo hành 5 năm</p>"
    r = _run("G2_claim_provenance", {"body_html": html})
    assert r.status == "blocked"          # detector, KHÔNG bao giờ fail khi SSOT chưa có
    assert len(r.violations) >= 2

def test_g2_pass_claim_with_id():
    html = '<p>Giá <span data-claim-id="PRICE_2026_OWNER">1.200.000đ</span></p>'
    r = _run("G2_claim_provenance", {"body_html": html})
    assert r.status == "pass"

def test_g2_pass_no_numeric_claim():
    r = _run("G2_claim_provenance", {"body_html": "<p>Phim cách nhiệt cao cấp</p>"})
    assert r.status == "pass"

def test_g2_is_detector_never_fail():
    r = _run("G2_claim_provenance", {"body_html": "<p>Giá 500.000đ không nguồn</p>"})
    assert r.status != "fail"


# ---------- G3_product_version (heuristic/warn — is_blocking=False) ----------
def test_g3_fail_mixed_years():
    html = "<td>CR BLK40 đời 2023 và 2026 dùng chung thông số</td>"
    r = _run("G3_product_version", {"body_html": html})
    assert r.status == "fail"

def test_g3_pass_single_year():
    r = _run("G3_product_version", {"body_html": "<td>CR BLK40 đời 2026</td>"})
    assert r.status == "pass"

def test_g3_is_advisory():
    assert REGISTRY["G3_product_version"].is_blocking is False


# ---------- G4_faq_1to1 (schema-dependent) ----------
def test_g4_blocked_no_jsonld():
    r = _run("G4_faq_1to1", {"body_html": "<h3>Câu hỏi?</h3><p>Trả lời.</p>", "jsonld": None})
    assert r.status == "blocked"

def test_g4_fail_mismatch():
    html = "<h3>Phim chặn bao nhiêu UV?</h3><p>99%.</p><h3>Bảo hành mấy năm?</h3><p>5 năm.</p>"
    jsonld = {"@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": "Phim chặn bao nhiêu UV?",
         "acceptedAnswer": {"@type": "Answer", "text": "99%."}},
    ]}
    r = _run("G4_faq_1to1", {"body_html": html, "jsonld": jsonld})
    assert r.status == "fail"

def test_g4_pass_1to1():
    html = "<h3>Phim chặn bao nhiêu UV?</h3><p>99%.</p><h3>Bảo hành mấy năm?</h3><p>5 năm.</p>"
    jsonld = {"@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": "Phim chặn bao nhiêu UV?",
         "acceptedAnswer": {"@type": "Answer", "text": "99%."}},
        {"@type": "Question", "name": "Bảo hành mấy năm?",
         "acceptedAnswer": {"@type": "Answer", "text": "5 năm."}},
    ]}
    r = _run("G4_faq_1to1", {"body_html": html, "jsonld": jsonld})
    assert r.status == "pass"


# ---------- G5_schema_entity (structural) ----------
def test_g5_blocked_no_jsonld():
    r = _run("G5_schema_entity", {"jsonld": None})
    assert r.status == "blocked"

def test_g5_fail_missing_type():
    r = _run("G5_schema_entity", {"jsonld": {"@graph": [{"name": "x"}]}})
    assert r.status == "fail"

def test_g5_pass_dual_typing():
    jsonld = {"@graph": [
        {"@type": "Article", "@id": "https://auto365.vn/a"},
        {"@type": ["OfferCatalog", "ItemList"], "@id": "https://auto365.vn/c"},
    ]}
    r = _run("G5_schema_entity", {"jsonld": jsonld})
    assert r.status == "pass"


# ---------- G7b_inline_style (warn — is_blocking=False) ----------
def test_g7b_fail_class_present():
    r = _run("G7b_inline_style", {"body_html": '<p class="lead">x</p>'})
    assert r.status == "fail"

def test_g7b_pass_inline_style():
    r = _run("G7b_inline_style", {"body_html": '<p style="margin:0">x</p>'})
    assert r.status == "pass"

def test_g7b_is_advisory():
    assert REGISTRY["G7b_inline_style"].is_blocking is False


# ---------- G8_eeat (structural) ----------
def test_g8_fail_empty_meta():
    r = _run("G8_eeat", {"body_html": "<p>x</p>", "meta": {}})
    assert r.status == "fail"
    assert len(r.violations) >= 2

def test_g8_pass_full_meta():
    ctx = {"body_html": "<p>x</p>", "meta": {
        "author": "Nguyễn A", "updated_date": "2026-08-01",
        "sources": ["https://tds.example/spec.pdf"]}}
    r = _run("G8_eeat", ctx)
    assert r.status == "pass"

def test_g8_pass_source_via_external_link():
    ctx = {"body_html": '<p>Xem <a href="https://nguon.vn/tds">TDS</a></p>',
           "meta": {"author": "Nguyễn A", "updated_date": "2026-08-01"}}
    r = _run("G8_eeat", ctx)
    assert r.status == "pass"


# ---------- run_all integration ----------
def test_run_all_registers_four_gates():
    results = run_all({"body_html": "<p>x</p>", "jsonld": {"@type": "Article"}, "meta": {}})
    ids = {r.rule_id for r in results}
    assert {"G9_no_raw_script", "G7_no_h1_in_body", "G6_table_a11y", "G5b_no_speakable"} <= ids

def test_run_all_registers_all_eleven_gates():
    ids = set(REGISTRY.keys())
    expected = {
        "G1_superlatives", "G2_claim_provenance", "G3_product_version", "G4_faq_1to1",
        "G5_schema_entity", "G5b_no_speakable", "G6_table_a11y", "G7_no_h1_in_body",
        "G7b_inline_style", "G8_eeat", "G9_no_raw_script",
    }
    assert expected <= ids
