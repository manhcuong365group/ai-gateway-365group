"""Gate engine core. Mỗi gate là pure function trên context {body_html, jsonld, meta}.

Chữ ký ổn định để POST /gates/evaluate tái dùng ở Phase 2 và Phase 3.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

Context = dict  # {"body_html": str, "jsonld": Optional[dict|list], "meta": dict}


@dataclass
class Violation:
    locator: str
    evidence: str


@dataclass
class GateResult:
    rule_id: str
    status: str  # "pass" | "fail" | "blocked"
    violations: list[Violation] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "status": self.status,
            "violations": [v.__dict__ for v in self.violations],
        }


@dataclass
class Gate:
    rule_id: str
    fn: Callable[[Context], GateResult]
    # Khớp cột gates.is_blocking (migrations/0001, DEFAULT true). Cùng một khái niệm,
    # hai nơi lưu: DB là SSOT, REGISTRY là bản chạy. is_blocking=False = gate advisory
    # (warn) — vẫn trả status="fail" khi có vi phạm nhưng KHÔNG chặn request-approval.
    is_blocking: bool = True


REGISTRY: dict[str, Gate] = {}


def gate(rule_id: str, blocking: bool = True):
    """Decorator đăng ký một gate vào REGISTRY.

    blocking: True = fail chặn request-approval (§6). False = advisory/warn — gate vẫn
    trả status="fail" (fact: có vi phạm) nhưng consumer KHÔNG chặn. Việc chặn do consumer
    tính: block khi (status=="fail" AND gate.is_blocking); blocked ⇒ cần người.
    """
    def deco(fn: Callable[[Context], GateResult]) -> Callable[[Context], GateResult]:
        REGISTRY[rule_id] = Gate(rule_id=rule_id, fn=fn, is_blocking=blocking)
        return fn
    return deco


def run_all(ctx: Context, only: Optional[list[str]] = None) -> list[GateResult]:
    """Chạy toàn bộ (hoặc tập con) gate đã đăng ký."""
    rule_ids = only or list(REGISTRY.keys())
    return [REGISTRY[rid].fn(ctx) for rid in rule_ids if rid in REGISTRY]
