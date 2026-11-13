"""Exact-version human review routes for the fifteen-gate manuscript workflow."""

import hmac
import os
from typing import Any, Dict

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from src.config import SQLITE_DB_PATH
from src.database.example_registry import ExampleRegistry
from src.orchestration.review_store import ReviewStore

router = APIRouter(prefix="/api/manuscript/review-v2", tags=["Scholarly Review"])


class HumanApproval(BaseModel):
    """Exact content decision and authenticated reviewer identity."""
    kind: str = Field(..., pattern="^(SCHOLAR|AUTHOR)$")
    version: int = Field(..., ge=1)
    content_sha256: str = Field(..., min_length=64, max_length=64)
    reviewer_name: str = Field(..., min_length=2)


def _authorize(kind: str, supplied: str | None) -> None:
    """Check role-specific secret supplied in a server-side HTTP header.

    ``kind`` is SCHOLAR or AUTHOR and ``supplied`` is untrusted. Returns None;
    absent config or mismatch raises 403. Debug environment reference names,
    never print or log the secret value.
    """
    expected = os.getenv(f"REVIEW_{kind}_TOKEN", "")
    if not expected or not supplied or not hmac.compare_digest(expected, supplied):
        raise HTTPException(403, detail={"error": True, "code": "REVIEW_FORBIDDEN",
                                         "message": "Reviewer credential required"})


@router.post("/{unit_id}/approve")
def approve_exact_version(unit_id: str, payload: HumanApproval,
                          x_review_token: str | None = Header(default=None)) -> Dict[str, Any]:
    """Record scholar then author approval for the exact latest version.

    ``unit_id`` is a logical chapter; payload includes version/hash/reviewer and
    role secret is in X-Review-Token. Returns state without the credential;
    invalid sequence or stale hash is 409. Inspect stored state/version to debug.
    """
    _authorize(payload.kind, x_review_token)
    store = ReviewStore(SQLITE_DB_PATH)
    try:
        store.approve(unit_id, payload.version, payload.kind,
                      payload.reviewer_name, payload.content_sha256,
                      ExampleRegistry(SQLITE_DB_PATH) if payload.kind == "AUTHOR" else None)
        return {"unit_id": unit_id, "version": payload.version,
                "state": store.get_version(unit_id, payload.version)["state"]}
    except ValueError as exc:
        raise HTTPException(409, detail={"error": True, "code": "REVIEW_CONFLICT",
                                         "message": str(exc)}) from exc


@router.get("/{unit_id}/{version}")
def get_exact_version(unit_id: str, version: int,
                      x_review_token: str | None = Header(default=None)) -> Dict[str, Any]:
    """Return one version only to a credentialed scholar or author.

    Inputs identify exact content and reviewer secret; returns stored version.
    Missing/unauthorized content raises 403 or 404. Check unit/version in the
    review store for diagnostics without disclosing credentials.
    """
    author, scholar = os.getenv("REVIEW_AUTHOR_TOKEN", ""), os.getenv("REVIEW_SCHOLAR_TOKEN", "")
    if not x_review_token or not any(secret and hmac.compare_digest(secret, x_review_token)
                                     for secret in (author, scholar)):
        raise HTTPException(403, detail={"error": True, "code": "REVIEW_FORBIDDEN",
                                         "message": "Reviewer credential required"})
    try:
        return ReviewStore(SQLITE_DB_PATH).get_version(unit_id, version)
    except ValueError as exc:
        raise HTTPException(404, detail={"error": True, "code": "VERSION_NOT_FOUND",
                                         "message": str(exc)}) from exc
