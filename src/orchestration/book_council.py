"""Durable four-voice deliberation followed by an independent book review."""

import hashlib
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, Mapping

from src.orchestration.book_acceptance import sutra_shape_issues


VOICES = ("narada", "shandilya", "researcher", "sutrakar")
STAGES = ("position", "challenge", "reply")


def reply_coverage(answer: object) -> set[str]:
    """Find the peers explicitly named in an untrusted reply answer.

    ``answer`` may be a peer-keyed map or a list of addressed challenges.
    Return covered role IDs; unknown formats return an empty set. Inspect the
    stored reply when a missing-peer error appears during a chapter resume.
    """
    if isinstance(answer, dict):
        return {name for key in answer for name in VOICES
                if key in {name, f"to_{name}"} or key.startswith(f"{name}_")}
    if isinstance(answer, list):
        return {name for item in answer if isinstance(item, dict)
                for name in VOICES
                if any(value == name or value.startswith(f"{name}_")
                       for key in ("from", "to", "challenger", "challenge_from")
                       if isinstance(value := item.get(key), str))}
    return set()


class BookCouncil:
    """Coordinate four scholarly voices without giving the verifier a council vote."""

    def __init__(self, path: Path, voices: Mapping[str, Callable], validator: Callable):
        """Bind four role callbacks and one independent validator to a local store.

        The path owns exact stage records. Invalid role sets raise ValueError;
        inspect the stage and chapter keys when resuming an interrupted run.
        """
        if set(voices) != set(VOICES):
            raise ValueError("Exactly four discussion voices are required")
        self.path, self.voices, self.validator = Path(path), voices, validator
        with sqlite3.connect(self.path) as db:
            db.execute("CREATE TABLE IF NOT EXISTS book_stages (chapter INTEGER NOT NULL, stage TEXT NOT NULL, role TEXT NOT NULL, request_hash TEXT NOT NULL, response_json TEXT NOT NULL, PRIMARY KEY(chapter,stage,role))")
            db.execute("CREATE TABLE IF NOT EXISTS book_invalid_stages (chapter INTEGER NOT NULL, stage TEXT NOT NULL, role TEXT NOT NULL, attempt INTEGER NOT NULL, error TEXT NOT NULL, response_json TEXT NOT NULL)")

    def _stage(self, number: int, stage: str, role: str, request: dict,
               callback: Callable[[dict], dict]) -> dict:
        """Reuse only an identical request and persist a valid structured answer.

        Inputs identify one chapter, stage, role and request. A mismatch or
        malformed answer raises after two proposal or three other attempts.
        Invalid responses remain in the ignored local diagnostic table; inspect
        its stage and error fields without exposing manuscript text or secrets.
        """
        digest = hashlib.sha256(json.dumps(request, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        with sqlite3.connect(self.path) as db:
            row = db.execute("SELECT request_hash,response_json FROM book_stages WHERE chapter=? AND stage=? AND role=?", (number, stage, role)).fetchone()
            if row:
                if row[0] != digest:
                    raise ValueError(f"Changed chapter {number} discussion request at {stage}/{role}")
                cached = json.loads(row[1])
                if stage == "proposal" or stage.startswith("composition"):
                    key = "proposed_sutra" if stage == "proposal" else "new_sutra"
                    failures = sutra_shape_issues(cached.get(key))
                    if failures:
                        raise ValueError(f"Cached chapter {number} {stage} fails short-sutra gate: {failures}")
                return cached
        answer = None
        for attempt in range(2 if stage == "proposal" else 3):
            prompt = request if attempt == 0 else {
                **request, "repair_feedback": error,
                "previous_invalid_response": answer,
                "instruction": "Correct only the stated validation problem and return a complete JSON object."}
            answer = callback(prompt)
            error = None
            if stage == "challenge" and isinstance(answer, dict):
                expected = set(VOICES) - {role}
                if set(answer) == expected:
                    answer = {"challenges": answer}
            if stage == "reply" and isinstance(answer, dict) and "answers" not in answer:
                expected = set(VOICES) - {role}
                if expected <= set(answer):
                    answer = {"answers": {peer: answer[peer] for peer in expected},
                              **{key: value for key, value in answer.items() if key not in expected}}
            if not isinstance(answer, dict) or not answer:
                error = f"Empty or malformed {stage}/{role} response"
            elif stage == "position" and role == "researcher":
                passages = request.get("sources", {}).get("registered_knowledge", {}).get("passages", [])
                source_ids = {item["source_id"] for item in passages}
                if source_ids and not any(source_id in json.dumps(answer, ensure_ascii=False)
                                          for source_id in source_ids):
                    error = "Researcher position must cite at least one retrieved registered source ID"
            elif stage == "challenge" and (
                    not isinstance(answer.get("challenges"), dict) or
                    set(answer["challenges"]) != set(VOICES) - {role} or
                    any(not isinstance(value, (str, dict, list)) or not value
                        for value in answer["challenges"].values())):
                error = (f"{role} must address every other voice by exact role key; "
                         f"received keys={list(answer.get('challenges', {})) if isinstance(answer.get('challenges'), dict) else type(answer.get('challenges')).__name__}")
            elif stage == "reply":
                missing = (set(VOICES) - {role}) - reply_coverage(answer.get("answers"))
                if missing:
                    error = f"{role} must answer all three peer challenges; missing={sorted(missing)}"
            elif stage == "proposal":
                failures = sutra_shape_issues(answer.get("proposed_sutra"))
                if failures:
                    error = f"Proposal fails short-sutra gate: {failures}"
            elif stage.startswith("composition"):
                required = {"new_sutra", "padaccheda", "anvaya", "nirukta", "translation_mr",
                            "derivation_mr", "explanation_mr", "narada_sutra", "shandilya_sutra",
                            "examples", "dos_mr", "donts_mr", "reflection_mr", "reader_action_mr"}
                if not required <= answer.keys():
                    error = f"Incomplete {stage}/{role} response: {sorted(required - answer.keys())}"
                else:
                    failures = sutra_shape_issues(answer.get("new_sutra"))
                    if failures:
                        error = f"Composition fails short-sutra gate: {failures}"
            if error is None and stage.startswith("independent_review") and answer.get("verdict") not in {"PASS", "REVIEW_REQUIRED"}:
                error = f"Invalid {stage}/{role} verdict"
            if error is None:
                break
            with sqlite3.connect(self.path) as db:
                db.execute("INSERT INTO book_invalid_stages VALUES (?,?,?,?,?,?)",
                           (number, stage, role, attempt + 1, error,
                            json.dumps(answer, ensure_ascii=False)))
        if error is not None:
            raise ValueError(error)
        with sqlite3.connect(self.path) as db:
            db.execute("INSERT INTO book_stages VALUES (?,?,?,?,?)", (number, stage, role, digest, json.dumps(answer, ensure_ascii=False)))
        return answer

    def run(self, number: int, brief: dict, sources: dict, prior: list[dict],
            used_examples: list[str]) -> dict:
        """Conduct reciprocal challenges, compose once, then obtain independent review.

        Returns the exact draft, discussion and validator judgment. Exceptions
        leave completed stages resumable; the validator cannot edit the draft.
        Inspect stored stages to diagnose a failed or paused chapter.
        """
        if number < 2 or number > 20 or not brief.get("reader_question"):
            raise ValueError("A planned new chapter between 2 and 20 is required")
        base = {"chapter": number, "brief": brief, "sources": sources,
                "prior_chapters": prior[-3:], "forbidden_examples": used_examples}
        transcript: dict[str, Any] = {}
        with ThreadPoolExecutor(max_workers=4) as pool:
            for stage in STAGES:
                def turn(voice: str) -> tuple[str, dict]:
                    """Return one role's stage answer after the prior round completes.

                    ``voice`` is one frozen council role. Stage errors propagate;
                    inspect its chapter/stage record and sanitized dispatch audit.
                    """
                    request = {**base, "stage": stage, "speaker": voice,
                               "discussion": transcript}
                    return voice, self._stage(number, stage, voice, request, self.voices[voice])

                transcript[stage] = dict(pool.map(turn, VOICES))
        proposal = self._stage(number, "proposal", "sutrakar",
                               {**base, "stage": "proposal", "discussion": transcript}, self.voices["sutrakar"])
        def peer_turn(voice: str) -> tuple[str, dict]:
            """Return one peer's review of the same Sutrakar proposal.

            ``voice`` is Narada, Shandilya or researcher. The result is a role
            and structured review; provider or schema errors stop composition.
            Inspect the role's local stage record before retrying.
            """
            request = {**base, "discussion": transcript, "proposal": proposal,
                       "stage": "peer_review", "speaker": voice}
            return voice, self._stage(number, "peer_review", voice, request, self.voices[voice])

        with ThreadPoolExecutor(max_workers=3) as pool:
            peer = dict(pool.map(peer_turn, VOICES[:-1]))
        draft = self._stage(number, "composition", "sutrakar",
                            {**base, "stage": "composition", "discussion": transcript, "proposal": proposal,
                             "peer_review": peer}, self.voices["sutrakar"])
        review = self._stage(number, "independent_review", "validator",
                             {**base, "stage": "independent_review", "discussion": transcript, "proposal": proposal,
                              "peer_review": peer, "draft": draft}, self.validator)
        return {"draft": draft, "review": review, "discussion": transcript,
                "proposal": proposal, "peer_review": peer}
