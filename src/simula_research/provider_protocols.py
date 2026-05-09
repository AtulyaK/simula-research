from __future__ import annotations

import hashlib
from typing import Literal, Protocol

CriticVerdict = Literal["accept", "reject"]


class CriticVerdictFn(Protocol):
    """Callable used by dual-critic adjudication (Issue #29); swap for tests or real providers."""

    def __call__(self, text: str, critic_id: str) -> CriticVerdict: ...


def hash_based_critic_verdict(text: str, critic_id: str) -> CriticVerdict:
    """Deterministic stub matching historical `dual_critic._decision_from_text` behavior."""
    digest = hashlib.sha1(f"{critic_id}::{text}".encode("utf-8")).hexdigest()
    return "accept" if int(digest[:2], 16) % 2 == 0 else "reject"
