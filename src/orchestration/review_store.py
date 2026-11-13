"""Version-bound human review and frozen publication manifest storage.

This store is additive: historical manuscript rows are never revalidated or changed.
"""

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterable


def fingerprint(content: Dict[str, Any]) -> str:
    """Return SHA-256 of canonical JSON for an exact manuscript version.

    ``content`` must be JSON serializable. TypeError propagates if it is not;
    compare canonical payloads when debugging a fingerprint mismatch. This is
    an integrity identifier, not proof of provenance or scholarly correctness.
    """
    data = json.dumps(content, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


class ReviewStore:
    """Own draft revisions and separate AI, scholar, author, publication states."""

    def __init__(self, path: str | Path):
        """Create additive review tables at ``path``; return a transactional store.

        SQLite errors propagate; inspect path and schema on failure. No historical
        manuscript rows or approvals are modified by this initialization.
        """
        self.path = Path(path)
        with self._connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS review_versions (
                    unit_id TEXT NOT NULL, version INTEGER NOT NULL,
                    content_json TEXT NOT NULL, content_sha256 TEXT NOT NULL,
                    policy_version TEXT NOT NULL, gates_json TEXT NOT NULL,
                    state TEXT NOT NULL, PRIMARY KEY(unit_id, version));
                CREATE TABLE IF NOT EXISTS review_approvals (
                    unit_id TEXT NOT NULL, version INTEGER NOT NULL,
                    content_sha256 TEXT NOT NULL, kind TEXT NOT NULL,
                    approved_by TEXT NOT NULL,
                    PRIMARY KEY(unit_id, version, kind));
                CREATE TABLE IF NOT EXISTS publication_manifests (
                    manifest_id TEXT PRIMARY KEY, manifest_json TEXT NOT NULL);
            """)

    @contextmanager
    def _connection(self):
        """Yield a SQLite transaction and close its connection on success or failure.

        No parameters; returns a connection in context. Exceptions rollback and
        propagate; inspect transaction errors rather than accepting a draft.
        """
        db = sqlite3.connect(self.path, timeout=10)
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def save_draft(self, unit_id: str, content: Dict[str, Any], report: Dict[str, Any]) -> int:
        """Append a draft version and invalidate earlier approval for current use.

        ``unit_id`` identifies the logical chapter; report must include all policy
        gates. Returns new version. Missing gate evidence raises ValueError and
        DB failures rollback; inspect policy version and gate statuses to debug.
        """
        from src.agents.acceptance_policy import GATE_NAMES, POLICY_VERSION
        gates = report.get("gates", {})
        if set(gates) != set(GATE_NAMES) or report.get("policy_version") != POLICY_VERSION:
            raise ValueError("Complete current policy report required")
        with self._connection() as db:
            db.execute("BEGIN IMMEDIATE")
            version = db.execute("SELECT COALESCE(MAX(version),0)+1 FROM review_versions WHERE unit_id=?",
                                 (unit_id,)).fetchone()[0]
            db.execute("INSERT INTO review_versions VALUES (?,?,?,?,?,?,?)",
                       (unit_id, version, json.dumps(content, ensure_ascii=False),
                        fingerprint(content), POLICY_VERSION, json.dumps(gates), "DRAFT"))
        return version

    def mark_ai_validated(self, unit_id: str, version: int) -> None:
        """Promote an exact draft only when every versioned gate is PASS.

        Inputs identify the immutable version; returns None. ValueError blocks
        missing or failed gates, and SQLite failures propagate. Inspect the stored
        gate JSON when debugging a refused transition.
        """
        with self._connection() as db:
            row = db.execute("SELECT gates_json FROM review_versions WHERE unit_id=? AND version=? AND state='DRAFT'",
                             (unit_id, version)).fetchone()
            if row is None or any(v != "PASS" for v in json.loads(row[0]).values()):
                raise ValueError("All fifteen gates must pass on this draft")
            db.execute("UPDATE review_versions SET state='AI_VALIDATED' WHERE unit_id=? AND version=?",
                       (unit_id, version))

    def approve(self, unit_id: str, version: int, kind: str, approver: str,
                content_sha256: str) -> None:
        """Bind scholar or author approval to an exact AI validated content hash.

        ``kind`` is SCHOLAR or AUTHOR. Returns None; mismatch, invalid sequence,
        and blank approver raise ValueError. Compare stored fingerprint and state
        to debug stale review decisions.
        """
        if kind not in {"SCHOLAR", "AUTHOR"} or not approver.strip():
            raise ValueError("Human approval kind and approver required")
        with self._connection() as db:
            row = db.execute("SELECT content_sha256,state FROM review_versions WHERE unit_id=? AND version=?",
                             (unit_id, version)).fetchone()
            newest = db.execute("SELECT MAX(version) FROM review_versions WHERE unit_id=?", (unit_id,)).fetchone()[0]
            if row is None or version != newest or row[0] != content_sha256 or row[1] not in {"AI_VALIDATED", "SCHOLAR_REVIEWED"}:
                raise ValueError("Approval must bind the current validated content")
            if kind == "AUTHOR" and not db.execute("SELECT 1 FROM review_approvals WHERE unit_id=? AND version=? AND kind='SCHOLAR'",
                                                    (unit_id, version)).fetchone():
                raise ValueError("Scholar review required before author approval")
            db.execute("INSERT INTO review_approvals VALUES (?,?,?,?,?)",
                       (unit_id, version, content_sha256, kind, approver))
            db.execute("UPDATE review_versions SET state=? WHERE unit_id=? AND version=?",
                       ("SCHOLAR_REVIEWED" if kind == "SCHOLAR" else "AUTHOR_APPROVED", unit_id, version))

    def freeze_manifest(self, manifest_id: str, units: Iterable[tuple[str, int]],
                        example_registry: Any) -> Dict[str, Any]:
        """Freeze exact current approved units and gates for publication.

        ``units`` lists logical ID/version pairs in book order; ``example_registry``
        rechecks actual committed named examples. Returns manifest content; stale,
        repeated, unapproved or unallocated versions raise and no manifest is
        stored. Inspect approvals, gate reports and allocations to debug.
        """
        entries = []
        with self._connection() as db:
            for unit_id, version in units:
                row = db.execute("SELECT content_json,content_sha256,gates_json,state FROM review_versions WHERE unit_id=? AND version=?",
                                 (unit_id, version)).fetchone()
                newest = db.execute("SELECT MAX(version) FROM review_versions WHERE unit_id=?", (unit_id,)).fetchone()[0]
                if row is None or version != newest or row[3] != "AUTHOR_APPROVED" or any(v != "PASS" for v in json.loads(row[2]).values()):
                    raise ValueError(f"Unapproved or stale manuscript unit: {unit_id}")
                if not db.execute("SELECT 1 FROM review_approvals WHERE unit_id=? AND version=? AND kind='AUTHOR' AND content_sha256=?",
                                  (unit_id, version, row[1])).fetchone():
                    raise ValueError("Missing exact author approval")
                entries.append({"unit_id": unit_id, "version": version,
                                "content_sha256": row[1], "content": json.loads(row[0]),
                                "gates": json.loads(row[2])})
            if not entries or len({e["unit_id"] for e in entries}) != len(entries):
                raise ValueError("Manifest requires distinct approved units")
            if example_registry is None:
                raise ValueError("Durable example registry required at publication")
            example_registry.verify_manifest(entries)
            manifest = {"manifest_id": manifest_id, "units": entries}
            db.execute("INSERT INTO publication_manifests VALUES (?,?)",
                       (manifest_id, json.dumps(manifest, ensure_ascii=False)))
        return manifest
