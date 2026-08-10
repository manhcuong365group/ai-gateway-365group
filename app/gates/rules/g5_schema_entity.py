"""G5_schema_entity — mỗi node trong @graph phải có @type (không bịa entity).

Phụ thuộc JSON-LD: ctx.jsonld is None ⇒ status="blocked" (structural, schema-dependent).
Dual-typing hợp lệ: @type là list non-empty (vd ["OfferCatalog","ItemList"]).
Bắt: node thiếu @type, @type rỗng, @id có mặt nhưng rỗng.
"""
from __future__ import annotations

import json

from app.gates.base import GateResult, Violation, gate


def _nodes(jsonld):
    if isinstance(jsonld, dict):
        if "@graph" in jsonld:
            g = jsonld["@graph"]
            return g if isinstance(g, list) else [g]
        return [jsonld]
    if isinstance(jsonld, list):
        return jsonld
    return []


def _valid_type(t) -> bool:
    if isinstance(t, str):
        return bool(t.strip())
    if isinstance(t, list):
        return len(t) > 0 and all(isinstance(x, str) and x.strip() for x in t)
    return False


@gate("G5_schema_entity")
def check(ctx: dict) -> GateResult:
    jsonld = ctx.get("jsonld")
    if jsonld is None:
        return GateResult("G5_schema_entity", "blocked",
                          [Violation("jsonld", "không có JSON-LD trong context (schema-dependent)")])
    if isinstance(jsonld, str):
        try:
            jsonld = json.loads(jsonld)
        except json.JSONDecodeError:
            return GateResult("G5_schema_entity", "blocked",
                              [Violation("jsonld", "JSON-LD không parse được")])

    vios: list[Violation] = []
    for i, node in enumerate(_nodes(jsonld)):
        if not isinstance(node, dict):
            continue
        if not _valid_type(node.get("@type")):
            vios.append(Violation(f"@graph[{i}]", "node thiếu/rỗng @type — có thể bịa entity"))
        if "@id" in node and not str(node.get("@id") or "").strip():
            vios.append(Violation(f"@graph[{i}]", "@id rỗng"))

    return GateResult("G5_schema_entity", "fail" if vios else "pass", vios)
