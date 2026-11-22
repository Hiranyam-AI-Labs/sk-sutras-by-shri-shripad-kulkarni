"""Offline integration contract for economical thematic batching."""

from copy import deepcopy
import pytest
from scripts.run_research_book import planned_batches, prompt_payload, stage_contract


def test_batches_stable_and_chapter_bounded():
    """A singleton pilot and <=5 related entries remain stable across resumes."""
    entries = [{"number": n, "chapter": 1 if n <= 8 else 2} for n in range(1, 14)]
    result = planned_batches(entries)
    assert [[e["number"] for e in group] for group in result] == [[1], [2,3,4,5,6], [7,8], [9,10,11,12,13]]
    assert [e for group in result for e in group] == entries
    with pytest.raises(ValueError):
        planned_batches([])


def test_compaction_keeps_current_entry_peer_arguments():
    """Trim unrelated batch text without losing any current four-voice responses."""
    voices = ("narada", "shandilya", "researcher", "sutrakar")
    discussion = {"_batch": {"audit": "retain only locally"},
                  "position": {v: {"positions": {"2": v+" current", "3": "other"}} for v in voices},
                  "reply": {v: {"answers": {p: {"2": p+" answer", "3": "other"} for p in voices if p != v}} for v in voices}}
    payload = {"number": 2, "discussion": discussion, "sources": {"proof": "canonical"}, "used_case_ids": [], "sources_by_entry": {"duplicate": "packet"}}
    before = deepcopy(payload)
    result = prompt_payload(payload)
    assert payload == before
    assert "_batch" not in result["discussion"]
    assert "sources_by_entry" not in result
    assert result["sources"] == payload["sources"]
    for voice in voices:
        assert result["discussion"]["position"][voice]["positions"] == {"2": voice+" current"}
        assert len(result["discussion"]["reply"][voice]["answers"]) == 3
        assert all(set(points) == {"2"} for points in result["discussion"]["reply"][voice]["answers"].values())


def test_batch_stage_schemas_and_entry_composition():
    """Batch instructions cover each numbered entry; composition keeps500wordgate."""
    for stage, field in (("position", "positions"), ("challenge", "challenges"), ("reply", "answers"), ("proposal", "proposals"), ("peer_review", "reviews")):
        assert field in stage_contract(stage, {"scope": "batch", "entry_numbers": [2,3,4,5,6], "speaker": "shandilya"})
    assert "550 Marathi words" in stage_contract("composition", {})


def test_exact_reply_skeleton_covers_all_three_peers_and_five_entries():
    """Recover the observed missing-number failure without inventing reply text."""
    import json
    instruction = stage_contract("reply", {"scope": "batch", "entry_numbers": [2,3,4,5,6], "speaker": "shandilya"})
    skeleton = json.loads(instruction.split("\n")[-1])
    assert set(skeleton["answers"]) == {"narada", "researcher", "sutrakar"}
    assert all(set(items) == {"2", "3", "4", "5", "6"} for items in skeleton["answers"].values())
