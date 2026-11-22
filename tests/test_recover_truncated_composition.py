"""Offline regression of the exact entry-22 truncation; no credentials/providers.

Read-only diagnosed evidence is copied into pytest directories. All mutations and
mock responses affect those copies only; production files and databases stay intact.
"""

import json
import hashlib
import sqlite3
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock

import pytest

from scripts import recover_truncated_composition as recovery
from src.orchestration.research_council import ResearchCouncil, _json


@pytest.fixture(scope="module")
def snapshot():
    """Snapshot only diagnosed immutable input files and original failed rows."""
    work = Path(__file__).resolve().parents[1] / "logs/author-research-generation-20261118"
    partial = Path("responses/022-composition-sutrakar-825f066d9c0d.partial.txt")
    if not (work / partial).exists():
        pytest.skip("Diagnosed entry-22 evidence is not available in this checkout")
    bound = recovery.prepare_recovery(work, 22, work / partial)
    with sqlite3.connect((work / "council.db").as_uri() + "?mode=ro", uri=True) as db:
        run = db.execute("SELECT * FROM research_runs WHERE number=22").fetchone()
        attempt = db.execute("SELECT * FROM research_attempts WHERE number=22 AND stage='composition' AND speaker='sutrakar'").fetchone()
    with sqlite3.connect((work / "dispatch.db").as_uri() + "?mode=ro", uri=True) as db:
        dispatch = db.execute("SELECT call_id,status,record_json FROM council_dispatch_audit WHERE call_id=?", (bound["dispatch_call_id"],)).fetchone()
    return bound, partial, {p: (work / p).read_bytes() for p in bound["input_sha256"]}, run, attempt, dispatch


@pytest.fixture
def case(tmp_path, snapshot):
    """Create an isolated failed checkpoint and a complete seven-field mock patch."""
    bound, relative, files, run, attempt, dispatch = snapshot
    for name, content in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    with sqlite3.connect(tmp_path / "council.db") as db:
        db.executescript("""
        CREATE TABLE research_runs(number INTEGER PRIMARY KEY,request_hash TEXT);
        CREATE TABLE research_attempts(number INTEGER,stage TEXT,speaker TEXT,attempt INTEGER,request_hash TEXT,state TEXT,response_json TEXT,error TEXT);
        CREATE TABLE research_stages(number INTEGER,stage TEXT,speaker TEXT,request_hash TEXT,response_json TEXT,PRIMARY KEY(number,stage,speaker));
        """)
        db.execute("INSERT INTO research_runs VALUES (?,?)", run)
        db.execute("INSERT INTO research_attempts VALUES (?,?,?,?,?,?,?,?)", attempt)
    with sqlite3.connect(tmp_path / "dispatch.db") as db:
        db.execute("CREATE TABLE council_dispatch_audit(call_id TEXT,status TEXT,record_json TEXT)")
        db.execute("INSERT INTO council_dispatch_audit VALUES (?,?,?)", dispatch)
    patch = {"comparative_mr": [{"source_id": ref, "explanation_mr": "मूळ विचाराची मर्यादा लक्षात घेऊन आधुनिक व्यवसायात उपयोग करा"}
                                for ref in bound["preserved"]["references"]],
             "case_ids": [c["case_id"] for c in bound["request"]["sources"]["examples"]],
             "dos_mr": ["टप्पे ठरवा", "पुरावा तपासा", "जोडणी तपासा"],
             "donts_mr": ["घाई टाळा", "दावे वाढवू नका", "पुरावा लपवू नका"],
             "application_mr": "व्यवसायात पुढील टप्प्याचा निर्णय पुराव्यावर घ्या",
             "action_mr": "आज जोडणीची चाचणी ठरवा", "summary_mr": "प्रगतीसाठी पुरावा तपासा"}
    response = {"provider": "anthropic", "model_id": "claude-sonnet-5-5", "was_truncated": False,
                "finish_reason": "end_turn", "content": json.dumps(patch, ensure_ascii=False)}
    return tmp_path, tmp_path / relative, deepcopy(bound), response, patch


def invoke(case, callback):
    """Invoke explicit recovery against only the test copy."""
    return recovery.recover_truncated_composition(case[0], 22, case[1], callback)


def test_exact_reconstruction_and_successful_checkpoint_reuse(case):
    """Preserve six fields/cases, verify request hash, and replay without more calls."""
    work, partial, bound, response, patch = case
    assert recovery.prepare_recovery(work, 22, partial) == bound
    assert bound["request_hash"] == "b344f20bca0f5aaa53bd8a5532cf2a75ec08349b1f216f2f856fe98b33d77cd9"
    assert len(bound["preserved"]["exposition"]) == 8

    def callback(system, prompt, **kwargs):
        """Assert durable reservation and exact bounded Sonnet settings before response."""
        assert system == bound["system"] and prompt == bound["prompt"]
        assert kwargs == {"model_id": "claude-sonnet-5-5", "effort": "medium", "max_output_tokens": 6000}
        with sqlite3.connect(work / "council.db") as db:
            assert db.execute(f"SELECT state FROM {recovery.TABLE}").fetchone() == ("RUNNING",)
        return response

    call = Mock(side_effect=callback)
    record = invoke(case, call)
    assert record["assessment"]["status"] == "PASS" and record["independent_review"] == "PENDING"
    assert invoke(case, call) == record and call.call_count == 1
    with sqlite3.connect(work / "council.db") as db:
        stage = db.execute("SELECT request_hash,response_json FROM research_stages").fetchone()
        assert db.execute("SELECT state,error FROM research_attempts").fetchone() == ("HARD_FAILED", recovery.ERROR)
    draft = json.loads(stage[1])
    assert {k: draft[k] for k in recovery.PRESERVED} == bound["preserved"]
    assert draft["examples"] == bound["request"]["sources"]["examples"]
    assert stage[0] == bound["request_hash"]
    council = object.__new__(ResearchCouncil)
    council.path = work / "council.db"
    no_call = Mock(side_effect=AssertionError("Must reuse successful stage"))
    assert council._stage(bound["request"], no_call) == draft
    no_call.assert_not_called()


@pytest.mark.parametrize("defect", ["rewrite", "missing", "case_ids", "comparison", "dos", "truncated", "wrong_model", "bad_json"])
def test_invalid_continuation_fails_without_checkpoint_or_retry(case, defect):
    """Reject changes to frozen fields, malformed patches, provenance and truncation."""
    work, partial, bound, response, patch = case
    if defect == "rewrite":
        patch["exposition"] = ["बदल"]
    elif defect == "missing":
        del patch["summary_mr"]
    elif defect == "case_ids":
        patch["case_ids"].reverse()
    elif defect == "comparison":
        patch["comparative_mr"][0]["source_id"] = "unknown"
    elif defect == "dos":
        patch["dos_mr"] = []
    elif defect == "truncated":
        response["was_truncated"] = True
    elif defect == "wrong_model":
        response["model_id"] = "different"
    response["content"] = "{" if defect == "bad_json" else json.dumps(patch)
    call = Mock(return_value=response)
    with pytest.raises(RuntimeError, match="no automatic retry"):
        invoke(case, call)
    with pytest.raises(RuntimeError, match="no automatic retry"):
        invoke(case, call)
    assert call.call_count == 1
    with sqlite3.connect(work / "council.db") as db:
        assert db.execute("SELECT COUNT(*) FROM research_stages").fetchone() == (0,)
        state, raw, error = db.execute(f"SELECT state,response_json,error FROM {recovery.TABLE}").fetchone()
        assert state == "FAILED" and json.loads(raw) == response and error
        assert db.execute("SELECT state FROM research_attempts").fetchone() == ("HARD_FAILED",)


@pytest.mark.parametrize("target", ["partial", "plan", "prior", "attempt", "dispatch", "entry_hash"])
def test_changed_evidence_rejected_before_spending(case, target):
    """Every original identity/provenance/input discrepancy prevents the callback."""
    work, partial, bound, response, patch = case
    if target == "partial":
        partial.write_text(partial.read_text(encoding="utf-8").replace("CMP027", "OTHER"), encoding="utf-8")
    elif target in ("plan", "prior"):
        path = work / ("plan.json" if target == "plan" else "entry-021.json")
        value = json.loads(path.read_text(encoding="utf-8"))
        if target == "plan":
            value["entries"][21]["title_mr"] += "बदल"
        else:
            value["draft"]["summary_mr"] += "बदल"
        path.write_text(json.dumps(value), encoding="utf-8")
    else:
        with sqlite3.connect(work / ("dispatch.db" if target == "dispatch" else "council.db")) as db:
            if target == "dispatch":
                db.execute("UPDATE council_dispatch_audit SET status='SUCCESS'")
            elif target == "entry_hash":
                db.execute("UPDATE research_runs SET request_hash='changed'")
            else:
                db.execute("UPDATE research_attempts SET request_hash='changed'")
    call = Mock(return_value=response)
    with pytest.raises(ValueError):
        invoke(case, call)
    call.assert_not_called()


@pytest.mark.parametrize("target", ["stage", "metadata", "response", "interruption", "provider_error"])
def test_replay_tamper_and_interruption_never_retry(case, target):
    """Never retry a failed/interrupted callback or accept altered successful evidence."""
    call = Mock(return_value=case[3])
    if target in ("interruption", "provider_error"):
        call.side_effect = KeyboardInterrupt() if target == "interruption" else RuntimeError("provider unavailable")
        with pytest.raises((KeyboardInterrupt, RuntimeError)):
            invoke(case, call)
    else:
        invoke(case, call)
        with sqlite3.connect(case[0] / "council.db") as db:
            if target == "stage":
                db.execute("UPDATE research_stages SET request_hash='changed'")
            elif target == "metadata":
                db.execute(f"UPDATE {recovery.TABLE} SET record_json='{{}}'")
            else:
                response = deepcopy(case[3])
                response["content"] = response["content"].replace("टप्पे ठरवा", "वेळ ठरवा")
                db.execute(f"UPDATE {recovery.TABLE} SET response_json=?", (_json(response),))
    with pytest.raises((ValueError, RuntimeError)):
        invoke(case, call)
    assert call.call_count == 1


@pytest.mark.parametrize("text", ['{}', '{"comparative', '{"title_mr": "broken', '{"title_mr":1,"title_mr":2,'])
def test_partial_parser_never_invents_completed_values(text):
    """Only the exact six-complete-field boundary is eligible for continuation."""
    with pytest.raises((ValueError, json.JSONDecodeError)):
        recovery.complete_prefix(text)


@pytest.fixture
def alias_case(case):
    """Retain the exact diagnosed alias failure from one mock continuation call."""
    patch = case[4]
    patch["comparative_mr"] = [{"reference_id": c["source_id"], "text_mr": c["explanation_mr"]}
                               for c in patch["comparative_mr"]]
    case[3]["content"] = json.dumps(patch, ensure_ascii=False)
    with pytest.raises(RuntimeError, match="no automatic retry"):
        invoke(case, Mock(return_value=case[3]))
    return case


def alias(case):
    """Invoke the callback-free alias entry point against the isolated test copy."""
    return recovery.recover_comparison_field_alias(case[0], 22, case[1])


def test_alias_recovery_preserves_failed_rows_values_and_normal_path(alias_case):
    """Normalize only keys; successful replay is immutable and needs no callback."""
    case = alias_case
    with sqlite3.connect(case[0] / "council.db") as db:
        failed = db.execute(f"SELECT * FROM {recovery.TABLE}").fetchall()
        attempts = db.execute("SELECT * FROM research_attempts").fetchall()
    record = alias(case)
    assert record["provider_calls"] == 0 and record["independent_review"] == "PENDING"
    assert alias(case) == record
    with sqlite3.connect(case[0] / "council.db") as db:
        assert db.execute(f"SELECT * FROM {recovery.TABLE}").fetchall() == failed
        assert db.execute("SELECT * FROM research_attempts").fetchall() == attempts
        draft = json.loads(db.execute("SELECT response_json FROM research_stages").fetchone()[0])
    assert {k: draft[k] for k in recovery.PRESERVED} == case[2]["preserved"]
    assert draft["comparative_mr"] == [{"source_id": c["reference_id"], "explanation_mr": c["text_mr"]}
                                       for c in case[4]["comparative_mr"]]
    no_call = Mock(side_effect=AssertionError("Never call a provider"))
    with pytest.raises(RuntimeError, match="no automatic retry"):
        invoke(case, no_call)  # Original FAILED path remains FAILED.
    no_call.assert_not_called()


@pytest.mark.parametrize("defect", ["wrong_id", "wrong_fields", "extra_field", "other_error", "binding", "duplicate", "other_defect"])
def test_alias_rejects_wrong_scope(alias_case, defect):
    """Wrong fields/IDs and failures beyond the alias diagnosis cannot be accepted."""
    case = alias_case
    with sqlite3.connect(case[0] / "council.db") as db:
        row = db.execute(f"SELECT binding_json,response_json,error FROM {recovery.TABLE}").fetchone()
        bound, response = json.loads(row[0]), json.loads(row[1])
        patch = json.loads(response["content"])
        comparison = patch["comparative_mr"][0]
        error = row[2]
        if defect == "wrong_id":
            comparison["reference_id"] = "UNKNOWN"
        elif defect == "wrong_fields":
            comparison["source_id"] = comparison.pop("reference_id")
        elif defect == "extra_field":
            comparison["extra"] = "ignored?"
        elif defect == "other_error":
            error += "; unrelated failure"
        elif defect == "binding":
            bound["request_hash"] = "changed"
        elif defect == "duplicate":
            patch["comparative_mr"].append(deepcopy(comparison))
        else:
            patch["dos_mr"] = []
        response["content"] = json.dumps(patch)
        db.execute(f"UPDATE {recovery.TABLE} SET binding_json=?,response_json=?,error=?",
                   (_json(bound), _json(response), error))
    with pytest.raises(ValueError):
        alias(case)
    with sqlite3.connect(case[0] / "council.db") as db:
        assert db.execute("SELECT COUNT(*) FROM research_stages").fetchone() == (0,)


@pytest.mark.parametrize("target", ["raw_bytes", "values", "audit", "stage"])
def test_alias_replay_rejects_tampering(alias_case, target):
    """Bind exact failed-response bytes, normalized values and successful stage."""
    case = alias_case
    alias(case)
    with sqlite3.connect(case[0] / "council.db") as db:
        if target == "raw_bytes":
            db.execute(f"UPDATE {recovery.TABLE} SET response_json=response_json || ' '")
        elif target == "audit":
            db.execute("UPDATE research_comparison_alias_recoveries SET record_json='{}'")
        elif target == "stage":
            db.execute("UPDATE research_stages SET request_hash='changed'")
        else:
            response = json.loads(db.execute(f"SELECT response_json FROM {recovery.TABLE}").fetchone()[0])
            patch = json.loads(response["content"])
            patch["comparative_mr"][0]["text_mr"] += " बदल"
            response["content"] = json.dumps(patch)
            db.execute(f"UPDATE {recovery.TABLE} SET response_json=?", (_json(response),))
    with pytest.raises(ValueError):
        alias(case)


@pytest.fixture
def ten_field_case(case):
    """Build the second diagnosed boundary in a copy of the bound entry-22 fixture."""
    work, partial, old_bound, response, patch = case
    preserved = {**old_bound["preserved"], **{k: patch[k] for k in recovery.MISSING[:4]}}
    text = '```json\n' + json.dumps(preserved, ensure_ascii=False)[:-1] + ', "application_mr": "अपूर्ण उपयोग'
    partial.write_text(text, encoding="utf-8")
    with sqlite3.connect(work / "dispatch.db") as db:
        record = json.loads(db.execute("SELECT record_json FROM council_dispatch_audit").fetchone()[0])
        record["response_sha256"] = hashlib.sha256(text.encode()).hexdigest()
        db.execute("UPDATE council_dispatch_audit SET record_json=?", (json.dumps(record),))
    bound = recovery.prepare_recovery(work, 22, partial)
    remaining = {k: patch[k] for k in recovery.MISSING[4:]}
    response["content"] = json.dumps(remaining, ensure_ascii=False)
    return work, partial, bound, response, remaining


def test_ten_field_boundary_preserves_all_values_and_only_requests_three(ten_field_case):
    """Complete only the three missing strings, preserving all ten decoded fields."""
    case = ten_field_case
    assert list(case[2]["preserved"]) == list(recovery.PRESERVED + recovery.MISSING[:4])
    prompt_data = json.loads(case[2]["prompt"].split("\nINPUT\n", 1)[1])
    assert prompt_data["missing_fields"] == list(recovery.MISSING[4:])
    assert prompt_data["completed_fields"] == case[2]["preserved"]
    call = Mock(return_value=case[3])
    record = invoke(case, call)
    assert record["assessment"]["status"] == "PASS"
    assert invoke(case, call) == record and call.call_count == 1
    with sqlite3.connect(case[0] / "council.db") as db:
        answer = json.loads(db.execute("SELECT response_json FROM research_stages").fetchone()[0])
        assert db.execute("SELECT state FROM research_attempts").fetchone() == ("HARD_FAILED",)
    assert {k: answer[k] for k in case[2]["preserved"]} == case[2]["preserved"]
    assert answer["application_mr"] == case[4]["application_mr"]


@pytest.mark.parametrize("defect", ["overwrite", "missing", "wrong_type", "case_drift"])
def test_ten_field_patch_rejects_changes_and_incomplete_output(ten_field_case, defect):
    """Extra preserved fields, missing strings and canonical-case drift fail closed."""
    bound = deepcopy(ten_field_case[2])
    patch = deepcopy(ten_field_case[4])
    if defect == "overwrite":
        patch["dos_mr"] = ["बदल"]
    elif defect == "missing":
        del patch["summary_mr"]
    elif defect == "wrong_type":
        patch["action_mr"] = []
    else:
        bound["preserved"]["case_ids"].reverse()
    with pytest.raises(ValueError):
        recovery._validate_patch(bound, patch)


@pytest.mark.parametrize("tail", ['"application_mr": 12', '"application_mr": "complete"',
                                  '"action_mr": "unfinished', '"application_mr": "bad\\q'])
def test_second_boundary_does_not_accept_other_json_failures(ten_field_case, tail):
    """Only an unterminated application string after ten complete fields qualifies."""
    prefix = json.dumps(ten_field_case[2]["preserved"], ensure_ascii=False)[:-1]
    with pytest.raises(ValueError):
        recovery.complete_prefix(prefix + ', ' + tail)


def test_original_22_prompt_and_binding_shape_stay_compatible(snapshot):
    """Existing paid entry-22 continuation retains its exact prompt and binding keys."""
    work = Path(__file__).resolve().parents[1] / "logs/author-research-generation-20261118"
    with sqlite3.connect((work / "council.db").as_uri() + "?mode=ro", uri=True) as db:
        row = db.execute(f"SELECT binding_json FROM {recovery.TABLE} WHERE number=22").fetchone()
    if row is None:
        pytest.skip("Original continuation record absent")
    old = json.loads(row[0])
    assert snapshot[0]["prompt"] == old["prompt"]
    assert set(snapshot[0]) == set(old)


def test_actual_36_readonly_preparation():
    """Verify actual entry-36 request/hash/partial evidence without any writes or calls."""
    work = Path(__file__).resolve().parents[1] / "logs/author-research-generation-20261118"
    partial = work / "responses/036-composition-sutrakar-313db5cee4c6.partial.txt"
    if not partial.exists():
        pytest.skip("Diagnosed entry-36 evidence absent")
    bound = recovery.prepare_recovery(work, 36, partial)
    assert list(bound["preserved"]) == list(recovery.PRESERVED + recovery.MISSING[:4])
    assert bound["model_id"] == "claude-sonnet-5-5" and bound["effort"] == "medium"
    assert bound["max_output_tokens"] == 6000
    assert json.loads(bound["prompt"].split("\nINPUT\n", 1)[1])["missing_fields"] == list(recovery.MISSING[4:])
