"""Durable cross-chapter identity and reservation registry for named examples.

The registry holds pending and committed allocations; publication must recheck it.
Human exception decisions are distinct from an AI verifier's opinion.
"""

import re
import json
import sqlite3
import unicodedata
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, Mapping


def normalize_entity(value: str) -> str:
    """Normalize a supplied name for identity matching; reject blank input.

    ``value`` is an editorial name, not a trusted identity. Returns a comparison
    key. ValueError means the editor must supply an identifiable name; inspect
    the source spelling and alias registry for debugging.
    """
    key = re.sub(r"[^\w]+", "", unicodedata.normalize("NFKC", value).casefold())
    if not key:
        raise ValueError("Example entity name must not be blank")
    return key


class ExampleRegistry:
    """Own SQLite identity, aliases, reservations, and explicit author exceptions."""

    @contextmanager
    def _connection(self, **kwargs):
        """Yield one SQLite transaction and close its handle on every path.

        ``kwargs`` are sqlite3.connect options; returns a connection in context.
        Exceptions propagate after rollback. Check open handles if a Windows
        test database cannot be removed after the context exits.
        """
        db = sqlite3.connect(self.path, **kwargs)
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def __init__(self, path: str | Path):
        """Open a project-owned SQLite path and ensure transactional tables exist.

        ``path`` must identify the intended database. Returns a registry handle;
        SQLite errors propagate and block allocation. Check path permissions and
        journal state to debug failures without exposing manuscript text.
        """
        self.path = Path(path)
        with self._connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS example_entities (
                    identity TEXT PRIMARY KEY, kind TEXT NOT NULL,
                    canonical_name TEXT NOT NULL, provenance TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS example_aliases (
                    alias TEXT PRIMARY KEY, identity TEXT NOT NULL REFERENCES example_entities(identity));
                CREATE TABLE IF NOT EXISTS example_allocations (
                    chapter TEXT NOT NULL, identity TEXT NOT NULL,
                    polarity TEXT NOT NULL, location TEXT NOT NULL,
                    content_sha256 TEXT NOT NULL,
                    state TEXT NOT NULL CHECK(state IN ('RESERVED','COMMITTED')),
                    PRIMARY KEY(chapter, identity, location));
                CREATE TABLE IF NOT EXISTS example_exceptions (
                    chapter TEXT NOT NULL, identity TEXT NOT NULL,
                    content_sha256 TEXT NOT NULL,
                    prior_chapters TEXT NOT NULL, distinct_event TEXT NOT NULL,
                    alternatives TEXT NOT NULL, necessity TEXT NOT NULL,
                    approved_by TEXT NOT NULL, PRIMARY KEY(chapter, identity, content_sha256));
                CREATE TABLE IF NOT EXISTS example_relations (
                    left_identity TEXT NOT NULL, right_identity TEXT NOT NULL,
                    relationship TEXT NOT NULL,
                    PRIMARY KEY(left_identity,right_identity));
            """)

    def register(self, name: str, kind: str, provenance: str, aliases: Iterable[str] = ()) -> str:
        """Register a person or business with provenance and known aliases.

        Inputs are editorial metadata; returns stable normalized identity.
        Conflicting aliases or missing provenance raise and rollback. Inspect
        aliases and source references to resolve collisions.
        """
        if kind not in {"PERSON", "BUSINESS"} or not provenance.strip():
            raise ValueError("Entity needs PERSON/BUSINESS kind and provenance")
        identity = f"{kind.lower()}:{normalize_entity(name)}"
        with self._connection() as db:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("INSERT OR IGNORE INTO example_entities VALUES (?,?,?,?)",
                       (identity, kind, name, provenance))
            for alias in (name, *aliases):
                db.execute("INSERT INTO example_aliases VALUES (?,?) ON CONFLICT(alias) DO UPDATE SET identity=excluded.identity WHERE identity=excluded.identity",
                           (normalize_entity(alias), identity))
                row = db.execute("SELECT identity FROM example_aliases WHERE alias=?", (normalize_entity(alias),)).fetchone()
                if row[0] != identity:
                    raise ValueError(f"Alias collision: {alias}")
        return identity

    def approve_exception(self, chapter: str, name: str, prior_chapters: str,
                          distinct_event: str, alternatives: str, necessity: str,
                          approved_by: str, content_sha256: str) -> None:
        """Record exact author permission for a repeated entity and chapter.

        All rationale fields and approver are required; returns None. Missing
        fields raise ValueError. Review the chapter and identity in the table to
        debug; this API is for authenticated author action, never an AI agent.
        """
        if not all(v.strip() for v in (chapter, prior_chapters, distinct_event,
                                       alternatives, necessity, approved_by, content_sha256)):
            raise ValueError("Repeat exception requires full rationale and author approval")
        identity = self.resolve(name)
        with self._connection() as db:
            db.execute("INSERT OR REPLACE INTO example_exceptions VALUES (?,?,?,?,?,?,?,?)",
                       (chapter, identity, content_sha256, prior_chapters, distinct_event,
                        alternatives, necessity, approved_by))

    def relate(self, person_or_business: str, related_name: str, relationship: str) -> None:
        """Record an editorial connection requiring cross-chapter review.

        Names must be registered and relationship nonblank. Returns None;
        unknown entities fail. Inspect identities and provenance to debug links.
        """
        if not relationship.strip():
            raise ValueError("Relationship rationale required")
        left, right = self.resolve(person_or_business), self.resolve(related_name)
        with self._connection() as db:
            db.execute("INSERT OR REPLACE INTO example_relations VALUES (?,?,?)",
                       (left, right, relationship))

    def resolve(self, name: str) -> str:
        """Return registered identity for a name or alias; unknown names fail.

        ``name`` is an editorial label. ValueError prevents unreviewed examples;
        register the entity with provenance to resolve it.
        """
        with self._connection() as db:
            row = db.execute("SELECT identity FROM example_aliases WHERE alias=?",
                             (normalize_entity(name),)).fetchone()
        if row is None:
            raise ValueError(f"Unregistered example: {name}")
        return row[0]

    def reserve(self, chapter: str, examples: Iterable[Mapping[str, str]], content_sha256: str) -> None:
        """Atomically reserve every named person and business in a chapter.

        Each mapping needs name, polarity and location. Same-chapter reuse is
        allowed; cross-chapter reuse needs an author exception. IntegrityError
        or ValueError rolls back the full batch. Inspect allocation and alias
        rows when resolving a conflict; retry only after editorial action.
        """
        if not content_sha256.strip():
            raise ValueError("Exact content fingerprint required")
        with self._connection(timeout=10, isolation_level=None) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                db.execute("DELETE FROM example_allocations WHERE chapter=? AND state='RESERVED' AND content_sha256<>?",
                           (chapter, content_sha256))
                for example in examples:
                    identity = self.resolve(example["name"])
                    related = [row[0] for row in db.execute(
                        "SELECT right_identity FROM example_relations WHERE left_identity=? UNION SELECT left_identity FROM example_relations WHERE right_identity=?",
                        (identity, identity)).fetchall()]
                    prior = {row[0] for row in db.execute(
                        f"SELECT DISTINCT chapter FROM example_allocations WHERE identity IN ({','.join('?' for _ in [identity,*related])}) AND chapter<>?",
                        (identity, *related, chapter)).fetchall()}
                    exception = db.execute("SELECT prior_chapters FROM example_exceptions WHERE chapter=? AND identity=? AND content_sha256=?",
                                           (chapter, identity, content_sha256)).fetchone()
                    if prior and (not exception or set(json.loads(exception[0])) != prior):
                        raise ValueError(f"Cross-chapter example repeat: {example['name']}")
                    db.execute("INSERT OR IGNORE INTO example_allocations VALUES (?,?,?,?,?,?)",
                               (chapter, identity, example["polarity"], example["location"], content_sha256, "RESERVED"))
                db.commit()
            except Exception:
                db.rollback()
                raise

    def release(self, chapter: str) -> None:
        """Release rejected draft reservations for ``chapter``; keep committed rows.

        Returns None. SQLite errors propagate; inspect state before retrying a
        rejected chapter so publication history remains intact.
        """
        with self._connection() as db:
            db.execute("DELETE FROM example_allocations WHERE chapter=? AND state='RESERVED'", (chapter,))

    def commit(self, chapter: str) -> None:
        """Commit a reviewed chapter's reservations without altering other chapters.

        Returns None; missing reservations raise ValueError. Check the chapter's
        reservation transaction and approval version to debug a missing row.
        """
        with self._connection() as db:
            count = db.execute("UPDATE example_allocations SET state='COMMITTED' WHERE chapter=? AND state='RESERVED'", (chapter,)).rowcount
            if not count:
                raise ValueError("No reserved examples to commit")

    def verify_manifest(self, entries: Iterable[Mapping[str, object]]) -> None:
        """Recheck exact approved chapter names against committed allocations.

        Each entry has unit_id, content_sha256 and content.named_examples with
        name, polarity and location. Returns None; stale allocations, omissions,
        repeats or related entities without exact exceptions raise ValueError.
        Inspect chapter, alias and exception rows to debug publication refusal.
        """
        seen = {}
        with self._connection() as db:
            for entry in entries:
                chapter, digest = str(entry["unit_id"]), str(entry["content_sha256"])
                content = entry["content"]
                examples = content.get("named_examples") if isinstance(content, dict) else None
                if not isinstance(examples, list) or not examples:
                    raise ValueError(f"Named example inventory missing: {chapter}")
                expected = {(self.resolve(e["name"]), e["polarity"], e["location"])
                            for e in examples}
                actual = set(db.execute("SELECT identity,polarity,location FROM example_allocations WHERE chapter=? AND content_sha256=? AND state='COMMITTED'",
                                        (chapter, digest)).fetchall())
                if expected != actual:
                    raise ValueError(f"Stale or missing example allocations: {chapter}")
                for identity, _, _ in expected:
                    related = {r[0] for r in db.execute(
                        "SELECT right_identity FROM example_relations WHERE left_identity=? UNION SELECT left_identity FROM example_relations WHERE right_identity=?",
                        (identity, identity)).fetchall()}
                    prior = {prior_chapter for prior_identity, prior_chapter in seen.items()
                             if prior_identity == identity or prior_identity in related}
                    if prior:
                        row = db.execute("SELECT prior_chapters FROM example_exceptions WHERE chapter=? AND identity=? AND content_sha256=?",
                                         (chapter, identity, digest)).fetchone()
                        if not row or set(json.loads(row[0])) != prior:
                            raise ValueError(f"Unapproved book-wide example repeat: {identity}")
                    seen[identity] = chapter

    def allocated_entities(self) -> list[dict]:
        """List reserved and committed named entities for research and authorship.

        Returns name/kind/chapter/state rows without private source text. SQLite
        errors propagate; inspect the allocation table to debug stale advice.
        """
        with self._connection() as db:
            rows = db.execute("SELECT e.canonical_name,e.kind,a.chapter,a.state FROM example_allocations a JOIN example_entities e ON e.identity=a.identity ORDER BY a.chapter").fetchall()
        return [{"name": row[0], "kind": row[1], "chapter": row[2], "state": row[3]}
                for row in rows]
