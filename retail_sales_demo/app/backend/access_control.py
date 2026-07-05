"""Phase 3 access control: store-level filtering, PII masking, role checks.

*** FALLBACK IMPLEMENTATION — NOT THE PREFERRED APPROACH ***
The preferred approach (per docs/phase3_governance_and_ops.md) is Unity
Catalog row filters / column masks enforced at the database layer. This
session has no network access to the Databricks workspace, so it was
impossible to verify whether those features are available on this
workspace's edition. This module is the documented fallback: enforcement
happens here, in the API layer, using one shared app identity to query the
Warehouse — it is NOT a database-level guarantee. See the "重要なセキュリティ
上の注意" section of docs/phase3_governance_and_ops.md before relying on this
for anything beyond a demo.

Identity resolution: Databricks Apps is expected to forward the signed-in
user's email via an `X-Forwarded-Email` header when the app has user
authorization configured. That header name is ALSO UNVERIFIED against a
live deployment — confirm it against the real request headers once this can
be deployed, and adjust `_HEADER_NAME` if it differs.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

from fastapi import Request

from . import config, queries
from .db import run_query

_HEADER_NAME = "X-Forwarded-Email"
_CACHE_TTL_SECONDS = 60
_ALL_STORES_MARKER = "ALL"

PII_VIEWER_ROLE = "PII_VIEWER"
AUDIT_VIEWER_ROLE = "AUDIT_VIEWER"


@dataclass
class AccessContext:
    user_email: str
    allowed_store_ids: Optional[list[str]]  # None means "every store" (admin/HQ)
    roles: set[str] = field(default_factory=set)

    @property
    def can_view_pii(self) -> bool:
        return PII_VIEWER_ROLE in self.roles or self.allowed_store_ids is None

    @property
    def can_view_audit_log(self) -> bool:
        return AUDIT_VIEWER_ROLE in self.roles or self.allowed_store_ids is None


class _TTLCache:
    def __init__(self, ttl_seconds: float):
        self._ttl = ttl_seconds
        self._store: dict[str, tuple[float, object]] = {}

    def get(self, key: str):
        entry = self._store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if time.monotonic() > expires_at:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: object) -> None:
        self._store[key] = (time.monotonic() + self._ttl, value)


_mapping_cache = _TTLCache(_CACHE_TTL_SECONDS)


def resolve_user_email(request: Request) -> str:
    return request.headers.get(_HEADER_NAME) or config.DEMO_USER_EMAIL


def _fetch_allowed_store_ids(user_email: str) -> Optional[list[str]]:
    sql, params = queries.build_user_store_mapping_query(user_email)
    rows = run_query(sql, params)
    store_ids = [row["store_id"] for row in rows]
    if _ALL_STORES_MARKER in store_ids:
        return None
    return store_ids


def _fetch_roles(user_email: str) -> set[str]:
    sql, params = queries.build_user_role_mapping_query(user_email)
    rows = run_query(sql, params)
    return {row["role"] for row in rows}


def get_access_context(user_email: str) -> AccessContext:
    """Looks up the caller's allowed stores + roles, cached briefly to avoid a
    Warehouse round trip on every single request (these mappings change rarely)."""
    cached = _mapping_cache.get(user_email)
    if cached is not None:
        return cached  # type: ignore[return-value]

    allowed_store_ids = _fetch_allowed_store_ids(user_email)
    roles = _fetch_roles(user_email)
    context = AccessContext(user_email=user_email, allowed_store_ids=allowed_store_ids, roles=roles)
    _mapping_cache.set(user_email, context)
    return context


def resolve_effective_store_ids(
    requested_store_ids: Optional[list[str]], allowed_store_ids: Optional[list[str]]
) -> Optional[list[str]]:
    """Intersects the caller's request with what they're allowed to see.

    - allowed=None (admin/HQ): the request passes through unchanged.
    - allowed=[] (no rows in the mapping table): deny everything.
    - otherwise: intersect; an empty result means "no matching stores", which
      the caller should treat as "return nothing" rather than "return everything".
    """
    if allowed_store_ids is None:
        return requested_store_ids
    if not requested_store_ids:
        return allowed_store_ids
    return [s for s in requested_store_ids if s in allowed_store_ids]


def mask_customer_id(value: Optional[str]) -> Optional[str]:
    if not value:
        return value
    if len(value) <= 4:
        return "*" * len(value)
    return value[:4] + "*" * (len(value) - 4)
