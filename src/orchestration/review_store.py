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
                CREATE TABLE IF NOT EXISTS council_run_units (
                    run_id TEXT NOT NULL, unit_id TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    outcome_json TEXT, PRIMARY KEY(run_id, unit_id));
                CREATE TABLE IF NOT EXISTS council_attempt_corrections (
                    run_id TEXT NOT NULL, unit_id TEXT NOT NULL,
                    prior_attempts INTEGER NOT NULL, reason TEXT NOT NULL,
                    PRIMARY KEY(run_id, unit_id));
            """)

    def correct_precomposition_attempts(self, run_id: str, unit_id: str) -> int:
        """Reclassify old precomposition technical calls without resetting budget.

        This one-time migration applies only when no draft version exists and no
        terminal outcome was recorded. It records the prior count for audit and
        returns it; any actual composition blocks correction.
        """
        with self._connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT attempts,outcome_json FROM council_run_units WHERE run_id=? AND unit_id=?",
                             (run_id, unit_id)).fetchone()
            if (row is None or row[1] or not row[0] or
                    db.execute("SELECT 1 FROM review_versions WHERE unit_id=? LIMIT 1", (unit_id,)).fetchone() or
                    db.execute("SELECT 1 FROM council_attempt_corrections WHERE run_id=? AND unit_id=?",
                               (run_id, unit_id)).fetchone()):
                raise ValueError("Precomposition correction requires uncomposed, uncorrected run unit")
            db.execute("INSERT INTO council_attempt_corrections VALUES (?,?,?,?)",
                       (run_id, unit_id, row[0], "technical provider/schema failures before composition"))
            db.execute("UPDATE council_run_units SET attempts=0 WHERE run_id=? AND unit_id=?",
                       (run_id, unit_id))
        return row[0]

    def latest_state(self, unit_id: str) -> Dict[str, Any] | None:
        """Return the latest stored version/state or None without changing it."""
        with self._connection() as db:
            row = db.execute("SELECT version,state FROM review_versions WHERE unit_id=? ORDER BY version DESC LIMIT 1",
                             (unit_id,)).fetchone()
        return {"version": row[0], "state": row[1]} if row else None

    def run_progress(self, run_id: str, unit_id: str) -> Dict[str, Any] | None:
        """Read durable attempt count and terminal outcome for one run unit."""
        with self._connection() as db:
            row = db.execute("SELECT attempts,outcome_json FROM council_run_units WHERE run_id=? AND unit_id=?",
                             (run_id, unit_id)).fetchone()
        return {"attempts": row[0], "outcome": json.loads(row[1]) if row[1] else None} if row else None

    def start_attempt(self, run_id: str, unit_id: str, max_attempts: int) -> int:
        """Reserve the next numbered attempt durably before any role call.

        A crash consumes its attempt so a restart cannot silently replay paid
        work. Completed units and exhausted limits raise ValueError.
        """
        if not run_id or not unit_id:
            raise ValueError("Run and unit IDs required for durable attempt")
        with self._connection() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("INSERT OR IGNORE INTO council_run_units(run_id,unit_id) VALUES (?,?)",
                       (run_id, unit_id))
            attempts, outcome = db.execute(
                "SELECT attempts,outcome_json FROM council_run_units WHERE run_id=? AND unit_id=?",
                (run_id, unit_id)).fetchone()
            if outcome or attempts >= max_attempts:
                raise ValueError("Run unit already completed or attempt limit exhausted")
            db.execute("UPDATE council_run_units SET attempts=? WHERE run_id=? AND unit_id=?",
                       (attempts + 1, run_id, unit_id))
        return attempts + 1

    def finish_run_unit(self, run_id: str, unit_id: str, outcome: Dict[str, Any]) -> None:
        """Persist an immutable terminal outcome for a run unit."""
        with self._connection() as db:
            changed = db.execute(
                "UPDATE council_run_units SET outcome_json=? WHERE run_id=? AND unit_id=? AND outcome_json IS NULL",
                (json.dumps(outcome, ensure_ascii=False), run_id, unit_id)).rowcount
            if changed != 1:
                raise ValueError("Run unit absent or already completed")

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

    def get_version(self, unit_id: str, version: int) -> Dict[str, Any]:
        """Read one exact stored version for authenticated editorial review.

        Inputs identify unit/version. Returns content fingerprint and state;
        missing versions raise ValueError. Inspect unit ID and version to debug,
        never substitute a different current draft implicitly.
        """
        with self._connection() as db:
            row = db.execute("SELECT content_json,content_sha256,gates_json,state FROM review_versions WHERE unit_id=? AND version=?",
                             (unit_id, version)).fetchone()
        if row is None:
            raise ValueError("Review version not found")
        return {"unit_id": unit_id, "version": version, "content": json.loads(row[0]),
                "content_sha256": row[1], "gates": json.loads(row[2]), "state": row[3]}

    def current_formulations(self, exclude_unit_id: str | None = None) -> list[str]:
        """Return contemporary and historical Sanskrit for duplicate checks.

        ``exclude_unit_id`` avoids treating a retry as its own duplicate.
        Empty list means no stored candidates; inspect both manuscript tables
        if a historical phrase appears to be missing.
        """
        with self._connection() as db:
            rows = db.execute("SELECT content_json FROM review_versions v WHERE unit_id<>? AND version=(SELECT MAX(version) FROM review_versions WHERE unit_id=v.unit_id)",
                              (exclude_unit_id or "",)).fetchall()
            historical = []
            if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='manuscript_units'").fetchone():
                historical = [row[0] for row in db.execute(
                    "SELECT original_sanskrit_verse FROM manuscript_units WHERE original_sanskrit_verse IS NOT NULL").fetchall()]
        modern = [text for row in rows if isinstance((text := json.loads(row[0]).get("original_sanskrit_verse")), str) and text.strip()]
        return modern + [text for text in historical if isinstance(text, str) and text.strip()]

    def approve(self, unit_id: str, version: int, kind: str, approver: str,
                content_sha256: str, example_registry: Any = None) -> None:
        """Bind scholar or author approval to an exact AI validated content hash.

        ``kind`` is SCHOLAR or AUTHOR. The application supplies a registry for
        AUTHOR so exact example reservations commit in the same transaction.
        Mismatch, invalid sequence, and blank approver raise ValueError.
        """
        if kind not in {"SCHOLAR", "AUTHOR"} or not approver.strip():
            raise ValueError("Human approval kind and approver required")
        with self._connection() as db:
            if kind == "AUTHOR" and example_registry is not None:
                registry_path = Path(example_registry.path).resolve()
                if registry_path != self.path.resolve():
                    db.execute("ATTACH DATABASE ? AS examples_db", (str(registry_path),))
                allocation_table = ("example_allocations" if registry_path == self.path.resolve()
                                    else "examples_db.example_allocations")
            else:
                allocation_table = None
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT content_sha256,state FROM review_versions WHERE unit_id=? AND version=?",
                             (unit_id, version)).fetchone()
            newest = db.execute("SELECT MAX(version) FROM review_versions WHERE unit_id=?", (unit_id,)).fetchone()[0]
            if row is None or version != newest or row[0] != content_sha256 or row[1] not in {"AI_VALIDATED", "SCHOLAR_REVIEWED"}:
                raise ValueError("Approval must bind the current validated content")
            if kind == "AUTHOR" and not db.execute("SELECT 1 FROM review_approvals WHERE unit_id=? AND version=? AND kind='SCHOLAR'",
                                                    (unit_id, version)).fetchone():
                raise ValueError("Scholar review required before author approval")
            if allocation_table is not None:
                changed = db.execute(
                    f"UPDATE {allocation_table} SET state='COMMITTED' WHERE chapter=? AND content_sha256=? AND state='RESERVED'",
                    (unit_id, content_sha256)).rowcount
                if not changed:
                    raise ValueError("Exact draft example reservations required for author approval")
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

    def load_manifest(self, manifest_id: str, example_registry: Any) -> Dict[str, Any]:
        """Reload a frozen manifest and recheck current approvals and allocations.

        ``manifest_id`` identifies one stored edition; registry verifies named
        examples. Returns the stored object. Missing or stale units raise rather
        than silently exporting an obsolete draft.
        """
        with self._connection() as db:
            row = db.execute("SELECT manifest_json FROM publication_manifests WHERE manifest_id=?",
                             (manifest_id,)).fetchone()
            if row is None:
                raise ValueError("Frozen manifest not found")
            manifest = json.loads(row[0])
            for entry in manifest["units"]:
                unit_id, version, digest = entry["unit_id"], entry["version"], entry["content_sha256"]
                current = db.execute("SELECT MAX(version) FROM review_versions WHERE unit_id=?",
                                     (unit_id,)).fetchone()[0]
                approved = db.execute(
                    "SELECT 1 FROM review_versions v JOIN review_approvals a ON a.unit_id=v.unit_id AND a.version=v.version "
                    "WHERE v.unit_id=? AND v.version=? AND v.content_sha256=? AND v.state='AUTHOR_APPROVED' "
                    "AND a.kind='AUTHOR' AND a.content_sha256=?",
                    (unit_id, version, digest, digest)).fetchone()
                if current != version or not approved or fingerprint(entry["content"]) != digest:
                    raise ValueError(f"Frozen manifest unit is stale: {unit_id}")
        if example_registry is None:
            raise ValueError("Durable example registry required at export")
        example_registry.verify_manifest(manifest["units"])
        return manifest
