from app.gates.base import Gate, GateResult, Violation, REGISTRY, run_all
from app.gates.rules import (  # noqa: F401
    g1_superlatives,
    g2_claim_provenance,
    g3_product_version,
    g4_faq_1to1,
    g5_schema_entity,
    g5b_no_speakable,
    g6_table_a11y,
    g7_no_h1_in_body,
    g7b_inline_style,
    g8_eeat,
    g9_no_raw_script,
)

__all__ = ["Gate", "GateResult", "Violation", "REGISTRY", "run_all"]
