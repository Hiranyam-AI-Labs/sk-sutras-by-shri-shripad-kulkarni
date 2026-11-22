"""Resume a local 20-sutra, four-voice council and render unapproved v19 drafts."""

import json
import os
import sqlite3
import sys
import hashlib
from pathlib import Path
from typing import Any

from src.doc_export.author_book_v19 import render_book
from src.orchestration.book_acceptance import check_chapter
from src.orchestration.book_council import BookCouncil, VOICES
from src.orchestration.source_evidence import retrieve_passages
from src.providers.dispatch import BudgetedDispatcher
from src.providers.registry import ProviderRegistry


ROOT = Path(__file__).resolve().parents[1]
MODELS = {"narada": ("narada_specialist", "gemini-3.8-flash"),
          "shandilya": ("shandilya_specialist", "gpt-4o"),
          "researcher": ("bharatiya_jnana_specialist", "claude-sonnet-5-5"),
          "sutrakar": ("sutrakar_master", "claude-sonnet-5-5"),
          "validator": ("independent_validator", "gpt-4o")}
RATES = {"google:gemini-3.8-flash": {"input": .75, "output": 3.75, "effective_date": "2026-11-14"},
         "openai:gpt-4o": {"input": 2.5, "output": 10., "effective_date": "2026-11-14"},
         "anthropic:claude-sonnet-5-5": {"input": 2., "output": 10., "effective_date": "2026-11-14"}}


def load_project_credentials(folder: Path) -> None:
    """Load the four authorized project references only into this process.

    Missing or empty files raise before any provider call. Do not log their
    contents; inspect only file presence when debugging credential failures.
    """
    names = {"OPENAI_API_KEY": "openai_key.txt", "ANTHROPIC_API_KEY": "claude_key.txt",
             "GEMINI_API_KEY": "gemini_key.txt", "ANTHROPIC_WORKSPACE_ID": "claude_workspace_id.txt"}
    for variable, filename in names.items():
        value = (folder / filename).read_text(encoding="utf-8").strip()
        if not value:
            raise ValueError(f"Empty credential reference: {filename}")
        os.environ[variable] = value
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]


def parse_object(text: str) -> dict:
    """Decode one complete provider JSON object from untrusted response text.

    Surrounding prose or Markdown may appear. Returns the object; a missing,
    partial, second or non-object JSON payload raises ValueError so the
    caller can retry. Inspect the sanitized call audit for failure type and
    local invalid-stage ledger for schema diagnostics.
    """
    start = text.find("{")
    if start < 0:
        raise ValueError("Provider returned no JSON object")
    obj, end = json.JSONDecoder().raw_decode(text[start:])
    if not isinstance(obj, dict) or "{" in text[start + end:]:
        raise ValueError("Provider JSON was incomplete or contained another object")
    return obj


def registered_knowledge(brief: dict, template: Path) -> dict:
    """Retrieve theme-matched registered passages with verified file identities.

    Inputs are one reader brief and the supplied author Word template. Returns
    located excerpts, source cautions and template hash; missing or changed
    registered files raise. Inspect the source register before retrying.
    """
    register = json.loads((ROOT / "data/knowledge_repository/registry/source_register.json").read_text(encoding="utf-8"))
    files = {}
    metadata = {}
    for entry in register["documents"]:
        path = ROOT / entry["source_location"]
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != entry["sha256"]:
            raise ValueError(f"Registered source changed: {entry['document_id']}")
        files[entry["document_id"]] = path
        metadata[entry["document_id"]] = {"status": entry["status"],
                                          "known_conflicts": entry["known_conflicts"]}
    try:
        passages = retrieve_passages(files, brief["title_mr"] + " " + brief["reader_question"], limit=1)
    except ValueError as exc:
        if "No relevant passage found" not in str(exc):
            raise
        passages = []
    return {"passages": [{**passage, **metadata[passage["source_id"]]}
                         for passage in passages],
            "registered_source_ids": sorted(files),
            "author_template_sha256": hashlib.sha256(template.read_bytes()).hexdigest()}


def run_book(work: Path, template: Path, max_chapters: int = 20) -> dict[str, Any]:
    """Generate consecutive draft chapters with durable calls and exact local files.

    The user approved at most 20 total sutras. Existing role/model assignments are checked
    before calls. Each chapter and call can resume from SQLite; errors stop the
    run and keep completed drafts. No approval or publication is performed.
    Inspect report.json and the dispatch audit for any interrupted chapter.
    """
    if not 2 <= max_chapters <= 20:
        raise ValueError("Book run requires the preserved first chapter plus at most nineteen new chapters")
    work.mkdir(parents=True, exist_ok=True)
    load_project_credentials(Path(r"C:/Users/LENOVO/Dropbox/Hiranyam AI Labs/SK_Udyog_Sutras"))
    # Import provider SDK dependency graphs serially before concurrent council turns.
    import openai  # noqa: F401
    import anthropic  # noqa: F401
    from google import genai  # noqa: F401
    from google.genai import types  # noqa: F401
    registry = ProviderRegistry(offline_mode=False)
    for role, model in MODELS.values():
        if registry.get_adapter(role).model_id != model:
            raise ValueError("Five-agent model assignment changed")
    db = work / "book_council.db"
    # Large finite guard values satisfy the dispatch API without imposing a
    # practical token, call or dollar ceiling below the user's 20-sutra limit.
    dispatcher = BudgetedDispatcher(registry, RATES, 1_000_000., 10_000,
                                    audit_path=db, run_id="v19-full-book",
                                    max_elapsed_seconds=604800,
                                    role_timeouts={role: 240. for role, _ in MODELS.values()})
    narada = json.loads((ROOT / "data/raw/narada_bhakti_sutra.json").read_text(encoding="utf-8"))
    shandilya = json.loads((ROOT / "data/raw/shandilya_bhakti_sutra.json").read_text(encoding="utf-8"))
    roadmap = json.loads((ROOT / "data/book_roadmap_20.json").read_text(encoding="utf-8"))
    if len(roadmap) != 20 or [item.get("number") for item in roadmap] != list(range(1, 21)):
        raise ValueError("The reader roadmap must contain exactly 20 consecutive sutras")
    summaries = {"narada": [{"id": str(x["sutra_no"]), "text": x["sanskrit"],
                              "meaning": x.get("initial_meaning", {}).get("mr", "")} for x in narada],
                 "shandilya": [{"id": str(x["sutra_no"]), "text": x["sanskrit"],
                                 "meaning": x.get("initial_meaning", {}).get("mr", "")} for x in shandilya]}

    def request(voice: str, payload: dict) -> dict:
        """Send one role-specific stage through audited budget dispatch.

        Outputs must be complete JSON. Only composition has two separately
        reserved continuations. Inspect audit metadata for truncated calls.
        """
        role = MODELS[voice][0]
        stage = payload.get("stage", "")
        contract = {
            "position": "Return JSON with thesis, evidence, proposed_source_fit and concerns. Ground ancient meaning faithfully and propose the chapter's reader action.",
            "challenge": "Return JSON with a challenges object whose keys are exactly the other three role IDs from narada, shandilya, researcher, sutrakar (omit your own ID). Each value is a nonempty evidence-based question or reasoned agreement. Do not use display names as keys. No invented objections.",
            "reply": "Return JSON with answers mapping the exact other three role IDs to separate, evidence-based responses to their received challenges. Omit your own role ID. State unresolved points explicitly.",
            "proposal": "Sutrakar: return JSON with proposed_sutra, derivation, selected source IDs and unresolved objections; synthesize all four voices. The Sanskrit proposed_sutra must express one aphoristic business principle in two to four words and at most 32 Unicode characters excluding verse delimiters. Put qualifications and procedures in the Marathi explanation, not the sutra.",
            "peer_review": "Return JSON with supported points, objections, evidence, and whether the Sutrakar must revise before composition.",
            "composition": ("Return ONE JSON object with title_mr,new_sutra,padaccheda,anvaya,nirukta,translation_mr,derivation_mr,explanation_mr,"
                            "narada_sutra:{id,text,brief_meaning_mr},shandilya_sutra:{id,text,brief_meaning_mr},"
                            "examples:[{kind:'positive'|'cautionary',person,business,description_mr,source}],dos_mr:[three or more],donts_mr:[three or more],"
                            "reflection_mr,reader_action_mr. The newly formed Sanskrit new_sutra must express one aphoristic business principle in two to four words and at most 32 Unicode characters excluding verse delimiters, with no comma or multi-clause prose. Keep qualifications and procedures in the Marathi explanation."
                            " The main explanation_mr MUST be at least 500 Marathi whitespace-separated words,"
                            " substantive and practical. Source explanations are brief. Include at least one factual positive and one factual cautionary business case. Use distinct real business people and companies not in forbidden_examples."
                            " Preserve the exact supplied ancient Sanskrit text. No English translations. Include complete facts only with identifiable sources."
                            " Respond to peer challenges, keep the book's opening to closing journey. This is an unapproved draft."),
            "independent_review": "You are independent of the four voices. Judge ONLY the current draft in this request against the exact selected source texts and peer concerns. Do not repeat an objection about a prior proposal if the current draft resolved it; cite the exact current draft field for each issue. The new sutra MUST be an original composition, so originality alone is not a defect and it need not reuse every ancient word. Return JSON with verdict PASS or REVIEW_REQUIRED, issues array, evidence and unresolved_challenges. PASS means only that this automated review found no issue; the author still must approve. The Sanskrit line must be a two-to-four-word aphorism of at most 32 Unicode characters excluding delimiters, expressing one principle rather than a procedure. Check Sanskrit, source meanings, honest analogy, 500-word Marathi explanation, business action, distinct sourced examples, reader sequence and unresolved peer objections. Never approve on behalf of a human.",
            "source_selection": "Choose a defensible Narada and Shandilya source for this business chapter. Return JSON with narada_id,shandilya_id,reason. Do not force a connection; flag uncertainty."}
        kind = "independent_review" if stage.startswith("independent_review") else stage.split("_revision_")[0]
        brevity = (" Keep the entire response under 1,500 output tokens. Give one brief, "
                   "specific sentence per point. Do not repeat the input transcript or cite it at length."
                   if kind != "composition" else "")
        research_direction = (" As the researcher, analyze the located registered passages in sources.registered_knowledge."
                              " State which DOC IDs were relevant, which were superseded, and how their cautions constrain the business analogy."
                              " Do not manufacture a quotation or claim a source was consulted if no passage was retrieved."
                              if voice == "researcher" and kind == "position" else "")
        system = f"Role {voice}. {contract[kind]}{research_direction}{brevity} Return only a valid JSON object."
        provider_payload = payload
        if kind == "independent_review":
            provider_payload = {"stage": stage, "chapter": payload["chapter"],
                                "brief": payload["brief"], "sources": payload["sources"],
                                "draft": payload["draft"],
                                "peer_review": payload.get("peer_review", {}),
                                "instruction": "This is the current full draft. Assess only claims present here. A human Sanskrit scholar and author will still review it."}
        prompt = json.dumps(provider_payload, ensure_ascii=False, separators=(",", ":"))
        if kind == "composition":
            fragments = ""
            for _ in range(3):
                continuation = prompt if not fragments else prompt + "\nContinue this exact unfinished JSON after its last character, emitting only the suffix:\n" + fragments
                response = dispatcher.call(role, continuation, system,
                                           max_output_tokens=16384, allow_truncated=True)
                fragments += response.content
                if not response.was_truncated:
                    return parse_object(fragments)
            raise ValueError("Composition continuation limit reached")
        for attempt in range(3):
            correction = "" if attempt == 0 else "\nPrevious response could not be parsed as one complete JSON object. Return only the requested complete JSON object."
            response = dispatcher.call(role, prompt + correction, system,
                                       max_output_tokens=12288)
            try:
                return parse_object(response.content)
            except (ValueError, json.JSONDecodeError):
                if attempt == 2:
                    raise
        raise RuntimeError("Unreachable provider parsing loop")

    voices = {voice: (lambda payload, voice=voice: request(voice, payload)) for voice in VOICES}
    council = BookCouncil(db, voices, lambda payload: request("validator", {**payload, "stage": "independent_review"}))
    results = []
    prior = [{"number": 1, "title_mr": "उद्यम प्रेरणा स्फुरण आणि संकल्पसिद्धी",
              "new_sutra": "अथातो उद्यमजिज्ञासा", "reader_action_mr": "उद्योजकतेचा हेतू तपासा"}]
    identities = {"जमशेदजी टाटा", "tata", "नारायण मूर्ती", "infosys", "pets.com"}
    verses = {"अथातो उद्यमजिज्ञासा"}
    for brief in roadmap[1:max_chapters]:
        number = brief["number"]
        selection_request = {"stage": "source_selection", "brief": brief, "candidate_summaries": summaries}
        selection = council._stage(number, "source_selection", "researcher", selection_request,
                                   lambda p: request("researcher", p))
        selected = {}
        for corpus, key in (("narada", "narada_id"), ("shandilya", "shandilya_id")):
            options = {x["id"]: x for x in summaries[corpus]}
            if str(selection.get(key)) not in options:
                raise ValueError(f"Source selector chose unknown {corpus} ID")
            selected[corpus + "_sutra"] = options[str(selection[key])]
        source = {"narada_sutra": selected["narada_sutra"],
                  "shandilya_sutra": selected["shandilya_sutra"],
                  "selection_reason": selection.get("reason", ""),
                  "registered_knowledge": registered_knowledge(brief, template)}
        result = council.run(number, brief, source, prior, sorted(identities))
        draft = result["draft"]
        review = result["review"]
        revision_history = []
        stored_chapter = work / f"chapter-{number:02d}.json"
        if stored_chapter.exists():
            previous = json.loads(stored_chapter.read_text(encoding="utf-8"))
            if previous["brief"] != brief or previous["sources"] != source:
                raise ValueError(f"Chapter {number} saved brief or sources changed")
            draft = previous["draft"]
            review = previous["acceptance"]["independent_review"]
            revision_history = previous.get("revision_history", [])
        assessment = check_chapter(draft, source, identities, verses)
        numbered_attempts = [entry["attempt"] for entry in revision_history
                             if isinstance(entry.get("attempt"), int)]
        next_attempt = max(numbered_attempts, default=0) + 1
        for attempt in range(next_attempt, 7):
            if assessment["status"] == "READY_FOR_SCHOLAR_REVIEW" and review["verdict"] == "PASS":
                break
            if attempt > 3 and assessment["status"] == "READY_FOR_SCHOLAR_REVIEW":
                break
            feedback = {"acceptance_issues": assessment["issues"],
                        "validator_issues": review.get("issues", []),
                        "unresolved_challenges": review.get("unresolved_challenges", [])}
            revision_request = {"stage": f"composition_revision_{attempt}",
                                "chapter": number, "brief": brief, "sources": source,
                                "discussion": result["discussion"], "proposal": result["proposal"],
                                "peer_review": result["peer_review"], "previous_draft": draft,
                                "feedback": feedback, "forbidden_examples": sorted(identities),
                                "instruction": "Resolve every substantive issue. Preserve all source texts exactly. Return a full revised chapter JSON object."}
            revised = council._stage(number, f"composition_revision_{attempt}", "sutrakar",
                                     revision_request, lambda p: request("sutrakar", p))
            review_request = {"stage": f"independent_review_revision_{attempt}",
                              "chapter": number, "brief": brief, "sources": source,
                              "discussion": result["discussion"], "peer_review": result["peer_review"],
                              "draft": revised, "previous_feedback": feedback}
            review = council._stage(number, f"independent_review_revision_{attempt}", "validator",
                                    review_request, lambda p: request("validator", p))
            draft = revised
            assessment = check_chapter(draft, source, identities, verses)
            revision_history.append({"attempt": attempt, "assessment": assessment, "review": review})
        assessment["independent_review"] = review
        (work / f"chapter-{number:02d}.json").write_text(json.dumps(
            {"brief": brief, "sources": source, "draft": draft,
             "acceptance": assessment, "discussion": result["discussion"],
             "peer_review": result["peer_review"], "revision_history": revision_history}, ensure_ascii=False, indent=2), encoding="utf-8")
        if assessment["status"] != "READY_FOR_SCHOLAR_REVIEW":
            raise ValueError(f"Chapter {number} still fails deterministic acceptance after six loops; see local chapter JSON")
        prior.append({"number": number, "title_mr": brief["title_mr"],
                      "new_sutra": draft.get("new_sutra"),
                      "reader_action_mr": draft.get("reader_action_mr")})
        verses.add(str(draft.get("new_sutra", "")).strip())
        for example in draft.get("examples", []):
            if isinstance(example, dict):
                identities.update(str(example.get(k, "")).casefold().strip()
                                  for k in ("person", "business") if example.get(k))
        results.append({"number": number, "status": assessment["status"],
                        "review": review.get("verdict"), "issues": assessment["issues"]})
        drafts = [json.loads((work / f"chapter-{n:02d}.json").read_text(encoding="utf-8"))["draft"]
                  | {"number": n, "title_mr": roadmap[n-1]["title_mr"]}
                  for n in range(2, number + 1)]
        render_book(template, drafts, work / "Udyam_Sutre_v19_New_Book_DRAFT.docx")
        (work / "report.json").write_text(json.dumps({"chapters": results,
            "calls": dispatcher.calls, "estimated_reservations_usd": dispatcher.reserved_usd,
            "human_approval": "NOT_PERFORMED", "publication": "NOT_PERFORMED"},
            ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"chapter {number} stored, {assessment['status']}, calls {dispatcher.calls}", flush=True)
    return {"chapters": len(results), "calls": dispatcher.calls}


if __name__ == "__main__":
    target = int(os.getenv("BOOK_TARGET_CHAPTERS", "20"))
    working = ROOT / "logs" / "book-v19"
    try:
        result = run_book(working, Path(r"C:/Users/LENOVO/Downloads/Udyam_Sutre_Sampurna_Granth_v19.docx"), target)
        (working / "failure.json").unlink(missing_ok=True)
        print(json.dumps(result), flush=True)
    except Exception as exc:
        working.mkdir(parents=True, exist_ok=True)
        (working / "failure.json").write_text(json.dumps({"type": type(exc).__name__,
            "message": str(exc)}, ensure_ascii=False), encoding="utf-8")
        raise
