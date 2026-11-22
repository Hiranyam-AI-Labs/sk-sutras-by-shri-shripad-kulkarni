"""Exercise the real runner/export loops with providers replaced by offline fakes."""

import json
import sqlite3
from types import SimpleNamespace
import pytest
from scripts import run_research_book as runner
from scripts import export_research_book as exporter


@pytest.fixture
def offline_run(tmp_path, monkeypatch):
    """Prepare six synthetic candidates and forbid all real provider dispatch."""
    entries = [{"id": f"TEST-{n}", "number": n, "chapter": 1,
                "source_packet": {"references": [], "examples": []}} for n in range(1,7)]
    runner.save(tmp_path / "plan.json", {"entries": entries, "chapters": []})
    runner.save(tmp_path / "forbidden_formulas.json", [])
    runner.save(tmp_path / "source_catalog.json", {"references": [{"id": "CMP008"}], "groups": []})
    seen = {}
    class Registry:
        """Return configured identities only; no SDK clients are constructed."""
        def __init__(self, **kwargs):
            """Ignore offline configuration; this fake cannot dispatch."""
        def get_adapter(self, role):
            """Resolve the frozen role identity for runner preflight."""
            voice = next(v for v, pair in runner.MODELS.items() if pair[0] == role)
            return SimpleNamespace(model_id=runner.MODELS[voice][1], provider_name=runner.PROVIDERS[voice])
    class Dispatcher:
        """Provide an empty audit database for the real reporting path."""
        def __init__(self, registry, rates, budget, calls, path, *args):
            """Create only a local empty ledger; no remote operations."""
            self.calls, self.reserved_usd = 0, 0.
            with sqlite3.connect(path) as db:
                db.execute("CREATE TABLE IF NOT EXISTS council_dispatch_audit(reservation_usd REAL)")
        def preflight_roles(self, roles):
            """No-op because fake identities were already checked."""
        def call(self, *args, **kwargs):
            """Fail the test if any provider callback is accidentally reached."""
            raise AssertionError("Provider calls forbidden")
    class Council:
        """Return one deliberately nonpassing candidate while retaining inputs."""
        def __init__(self, *args, **kwargs):
            """Accept callback wiring without executing it."""
        def run_batch_discussion(self, *args):
            """Return local deliberation placeholders for policy testing only."""
            return {"discussion": {}, "proposal": {}, "peer_review": {}}
        def compose_entry(self, number, brief, sources, prior, forbidden, used, *args):
            """Capture prior exclusions and return the predetermined result."""
            seen[number] = (list(prior), set(used))
            ready = number not in seen.get("failures", {5})
            return {"status": "READY_FOR_AUTHOR_REVIEW" if ready else "NEEDS_REVIEW",
                    "draft": {"id": f"TEST-{number}", "number": number, "chapter": 1,
                              "new_sutra": f"formula{number}", "examples": [{"case_id": f"case{number}"}]},
                    "assessment": {"status": "PASS", "issues": []},
                    "review": {"verdict": "PASS" if ready else "REVIEW_REQUIRED", "issues": [] if ready else [{"reason": "unresolved"}]}}
    monkeypatch.setattr(runner, "WORK", tmp_path)
    monkeypatch.setattr(runner, "load_project_credentials", lambda path: None)
    monkeypatch.setattr(runner, "ProviderRegistry", Registry)
    monkeypatch.setattr(runner, "BudgetedDispatcher", Dispatcher)
    monkeypatch.setattr(runner, "ResearchSpendGuard", lambda *args: SimpleNamespace(reserved_usd=0.))
    monkeypatch.setattr(runner, "ResearchCouncil", Council)
    return tmp_path, seen


def test_nonpassing_candidate_is_quarantined_without_weakening_export(offline_run, monkeypatch):
    """Continue distinct candidates; export only PASS entries with auditable numbering."""
    path, seen = offline_run
    report = runner._run(6, 1., "offline", allow_exclusions=True)
    assert report["completed"] == [1,2,3,4,6]
    assert report["status"] == "READY_FOR_AUTHOR_REVIEW_WITH_EXCLUSIONS"
    assert [x["number"] for x in report["excluded"]] == [5]
    assert "formula5" in seen[6][0] and "case5" in seen[6][1]
    captures = []
    monkeypatch.setattr(exporter, "WORK", path)
    monkeypatch.setattr(exporter, "assess_research_entry", lambda *args: {"status": "PASS"})
    monkeypatch.setattr(exporter, "render_research_book", lambda opening, closing, entries, *args: captures.append(entries) or {})
    result = exporter.export(path / "not-a-real-document.docx", 6, allow_exclusions=True)
    assert [x["id"] for x in captures[0]] == ["TEST-1", "TEST-2", "TEST-3", "TEST-4", "TEST-6"]
    assert [x["number"] for x in captures[0]] == [1,2,3,4,5]
    assert result["excluded_from_book"][0]["source_number"] == 5
    assert json.loads((path / "entry-006.json").read_text())["draft"]["number"] == 6


def test_default_stops_at_first_nonpassing_candidate(offline_run):
    """The optional filtered-book policy cannot silently change strict pilot mode."""
    report = runner._run(6, 1., "offline-strict")
    assert report["status"] == "QUALITY_STOP"
    assert report["completed"] == [1,2,3,4]
    assert report["stopped_at"] == 5


def test_tenth_exclusion_stops_before_another_candidate(offline_run):
    """A flexible final count never authorizes unlimited rejected paid drafts."""
    path, seen = offline_run
    seen["failures"] = set(range(2, 24, 2))
    entries = [{"id": f"TEST-{n}", "number": n, "chapter": n,
                "source_packet": {"references": [], "examples": []}} for n in range(1,25)]
    runner.save(path / "plan.json", {"entries": entries, "chapters": []})
    report = runner._run(24, 1., "offline-bound", allow_exclusions=True)
    assert report["status"] == "QUALITY_STOP"
    assert len(report["excluded"]) == 10
    assert report["stopped_at"] == 20
    assert 21 not in seen
