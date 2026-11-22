"""Repair only chapter 2's short sutra using saved council evidence and a $1 cap."""

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Callable

from src.doc_export.author_book_v19 import render_book
from src.orchestration.book_acceptance import check_chapter, sutra_shape_issues
from src.orchestration.book_council import VOICES
from scripts.run_book_council_v19 import (MODELS, RATES, ROOT,
                                          load_project_credentials, parse_object)


WORK = ROOT / "logs/book-v19"
TEMPLATE = Path(r"C:/Users/LENOVO/Downloads/Udyam_Sutre_Sampurna_Granth_v19.docx")
FIELDS = ("new_sutra", "padaccheda", "anvaya", "nirukta",
          "translation_mr", "derivation_mr", "explanation_mr")
PILOT_LIMIT_USD = 1.0


def checkpoint(path: Path, request: dict, call: Callable[[dict], dict]) -> dict:
    """Reuse one exact paid response or save it before the next stage.

    The path belongs to this local pilot, request is a complete role payload,
    and call invokes one role. Return its JSON object; changed requests or
    malformed responses raise. Inspect the checkpoint hash before a resume.
    """
    digest = hashlib.sha256(json.dumps(request, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    if path.exists():
        stored = json.loads(path.read_text(encoding="utf-8"))
        if stored.get("request_sha256") != digest:
            raise ValueError(f"Changed pilot request at {path.name}")
        return stored["answer"]
    answer = call(request)
    if not isinstance(answer, dict) or not answer:
        raise ValueError(f"Malformed pilot answer at {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"request_sha256": digest, "answer": answer},
                               ensure_ascii=False, indent=2), encoding="utf-8")
    return answer


def chapter_two_record(work: Path) -> tuple[dict, str]:
    """Read the rejected chapter and verify its four-voice evidence before calls.

    Work is the ignored local run directory. Return the saved record and its
    SHA-256; missing discussion, peer review, or source data raises. Inspect
    chapter-02.json and the original council ledger before retrying.
    """
    path = work / "chapter-02.json"
    raw = path.read_bytes()
    record = json.loads(raw.decode("utf-8"))
    if set(record.get("discussion", {}).get("position", {})) != set(VOICES) or \
       set(record.get("discussion", {}).get("challenge", {})) != set(VOICES) or \
       set(record.get("discussion", {}).get("reply", {})) != set(VOICES) or \
       set(record.get("peer_review", {})) != set(VOICES[:-1]):
        raise ValueError("Chapter 2 saved four-agent discussion is incomplete")
    if not all(record.get("sources", {}).get(key, {}).get("text")
               for key in ("narada_sutra", "shandilya_sutra")):
        raise ValueError("Chapter 2 source sutras are missing")
    return record, hashlib.sha256(raw).hexdigest()


def plan(work: Path) -> dict:
    """Show the existing long verse and complete evidence without provider use.

    Work identifies the previous local run. Return measured pilot inputs;
    missing files or incomplete discussion raise before credential loading.
    Inspect the saved chapter and source packet if this dry run fails.
    """
    record, digest = chapter_two_record(work)
    verse = record["draft"]["new_sutra"]
    return {"chapter": 2, "original_sha256": digest,
            "original_sutra": verse,
            "original_sutra_characters": len(verse.strip().strip("।॥").strip()),
            "short_sutra_issues": sutra_shape_issues(verse),
            "saved_discussion_roles": list(VOICES),
            "saved_peer_review_roles": list(VOICES[:-1]),
            "cap_usd": PILOT_LIMIT_USD,
            "paid_roles": ["sutrakar", "validator"],
            "candidate_exists": (work / "short-sutra-pilot/chapter-02.json").exists()}


def generate_pilot(work: Path, template: Path,
                   compose: Callable[[dict], dict],
                   validate: Callable[[dict], dict],
                   exporter: Callable = render_book) -> dict:
    """Make one resumable chapter-2 candidate from cached four-agent debate.

    Compose and validate are the frozen Sutrakar and independent-validator
    callbacks. Return a local candidate with deterministic and validator
    results; two failed revisions raise without changing the original chapter.
    Inspect attempt checkpoints to resume without duplicate paid calls.
    """
    record, original_sha = chapter_two_record(work)
    folder = work / "short-sutra-pilot"
    final_path = folder / "chapter-02.json"
    output = folder / "Udyam_Sutre_Chapter_02_SHORT_PILOT_DRAFT.docx"
    if final_path.exists():
        stored = json.loads(final_path.read_text(encoding="utf-8"))
        if stored.get("original_sha256") != original_sha:
            raise ValueError("Saved pilot belongs to a changed original chapter")
        if not output.exists():
            exporter(template, [stored["draft"] | {"number": 2}], output)
        return stored
    prior_examples = {"जमशेदजी टाटा", "tata", "नारायण मूर्ती", "infosys", "pets.com"}
    original = record["draft"]
    feedback = record.get("acceptance", {}).get("independent_review", {}).get("issues", [])
    selected = None
    previous = original
    for attempt in (1, 2):
        request = {"stage": "short_sutra_repair", "chapter": 2,
                   "brief": record["brief"], "sources": record["sources"],
                   "four_agent_discussion": record["discussion"],
                   "peer_review": record["peer_review"],
                   "previous_draft": previous, "feedback": feedback,
                   "instruction": "Return only the seven specified replacement fields. Preserve the exact ancient source sutras, examples, do's, don'ts, reflection and reader action. Express one original business principle in a grammatical Sanskrit aphorism of two to four words and at most 32 Unicode characters, excluding verse delimiters. Move duty qualifications and procedures into Marathi prose. Revise dependent padaccheda, anvaya, nirukta, translation, derivation, and the full explanation so all refer to the new aphorism; explanation_mr must contain at least 500 Marathi words. Do not present this modern sutra as ancient scripture."}
        replacement = checkpoint(folder / f"composition-{attempt}.json", request, compose)
        missing = [field for field in FIELDS if not isinstance(replacement.get(field), str)
                   or not replacement[field].strip()]
        if missing:
            feedback = [f"Missing replacement fields: {missing}"]
            continue
        draft = deepcopy(original)
        draft.update({field: replacement[field] for field in FIELDS})
        assessment = check_chapter(draft, record["sources"], prior_examples,
                                   {"अथातो उद्यमजिज्ञासा"})
        if assessment["issues"]:
            feedback = assessment["issues"]
            previous = draft
            continue
        review_request = {"stage": "independent_short_sutra_review", "chapter": 2,
                          "brief": record["brief"], "sources": record["sources"],
                          "four_agent_discussion": record["discussion"],
                          "peer_review": record["peer_review"],
                          "draft": draft,
                          "instruction": "Independently assess only this revised chapter. Check 32-character/two-to-four-word aphoristic Sanskrit, grammar, originality, exact ancient texts, faithful Marathi dependent fields, 500-word explanation, business action and the unchanged examples. Return verdict PASS or REVIEW_REQUIRED with specific issues. You cannot approve on behalf of the author or scholar."}
        review = checkpoint(folder / f"validator-{attempt}.json", review_request, validate)
        if review.get("verdict") not in {"PASS", "REVIEW_REQUIRED"}:
            raise ValueError("Independent pilot review has no valid verdict")
        selected = {"chapter": 2, "original_sha256": original_sha,
                    "attempt": attempt, "draft": draft, "acceptance": assessment,
                    "independent_review": review, "human_approval": "NOT_PERFORMED",
                    "publication": "NOT_PERFORMED"}
        if review["verdict"] == "PASS":
            break
        feedback = review.get("issues", [])
        previous = draft
    if selected is None:
        raise ValueError("Two Sutrakar attempts failed chapter 2 deterministic acceptance")
    folder.mkdir(parents=True, exist_ok=True)
    final_path.write_text(json.dumps(selected, ensure_ascii=False, indent=2), encoding="utf-8")
    exporter(template, [selected["draft"] | {"number": 2}], output)
    return selected


def execute(work: Path, template: Path) -> dict:
    """Invoke only existing Sutrakar and validator models under the $1 ledger.

    Work and template identify local artifacts. Return the pilot result and
    reservation totals; missing credentials, model drift, provider failures,
    or exhausted cap raise. Inspect sanitized dispatch rows and checkpoints.
    """
    from src.providers.dispatch import BudgetedDispatcher
    from src.providers.registry import ProviderRegistry

    status = plan(work)
    if status["candidate_exists"]:
        return generate_pilot(work, template, lambda payload: {}, lambda payload: {})
    load_project_credentials(Path(r"C:/Users/LENOVO/Dropbox/Hiranyam AI Labs/SK_Udyog_Sutras"))
    registry = ProviderRegistry(offline_mode=False)
    for role, model in MODELS.values():
        if registry.get_adapter(role).model_id != model:
            raise ValueError("Five-agent model assignment changed")
    dispatcher = BudgetedDispatcher(registry, RATES, PILOT_LIMIT_USD, 4,
                                    audit_path=work / "book_council.db",
                                    run_id="v19-short-pilot-chapter-02-v1",
                                    max_elapsed_seconds=3600,
                                    role_timeouts={role: 240. for role, _ in MODELS.values()})

    def ask(voice: str, payload: dict, system: str, output_tokens: int) -> dict:
        """Use one frozen role and parse one complete JSON result.

        Voice chooses the existing role, payload is the exact checkpointed
        request, and output_tokens bounds the reservation. Provider or JSON
        failure raises; inspect the call ledger and saved attempt files.
        """
        response = dispatcher.call(MODELS[voice][0],
                                   json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                                   system, max_output_tokens=output_tokens)
        return parse_object(response.content)

    result = generate_pilot(
        work, template,
        lambda payload: ask("sutrakar", payload,
                            "You are the existing Sutrakar. Reuse the completed four-agent debate. Return one JSON object with exactly new_sutra,padaccheda,anvaya,nirukta,translation_mr,derivation_mr,explanation_mr. The sutra must be concise, original, grammatical and at most 32 Unicode characters excluding delimiters. The Marathi explanation must be at least 500 words. No other chapter fields may change.", 8192),
        lambda payload: ask("validator", payload,
                            "You are the existing independent fifth validator. Review the revised chapter without joining the four-agent debate. Return JSON with verdict PASS or REVIEW_REQUIRED, issues and evidence. Never grant author approval.", 2500))
    return {"result": result, "calls": dispatcher.calls,
            "estimated_reservations_usd": dispatcher.reserved_usd,
            "cap_usd": PILOT_LIMIT_USD}


def main() -> None:
    """Default to zero-cost planning and require --execute for the paid pilot.

    No parameters are required. Print sanitized status only; errors identify
    the failed stage. Inspect local short-sutra-pilot checkpoints to resume.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Run only chapter 2 under the $1 reservation cap")
    args = parser.parse_args()
    if not args.execute:
        print(json.dumps(plan(WORK), ensure_ascii=False, indent=2))
    else:
        result = execute(WORK, TEMPLATE)
        print(json.dumps({"chapter": 2, "sutra": result["result"]["draft"]["new_sutra"],
                          "verdict": result["result"]["independent_review"]["verdict"],
                          "acceptance": result["result"]["acceptance"]["status"],
                          "calls": result.get("calls", 0),
                          "estimated_reservations_usd": result.get("estimated_reservations_usd", 0)},
                         ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
