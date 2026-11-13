"""Injected, bounded five-role council with persistent review eligibility.

Provider calls are supplied by the caller; tests use deterministic fakes. This
service cannot grant scholar or author approval or publish a manuscript.
"""

from typing import Any, Callable, Dict, Iterable, List, Mapping

from src.agents.acceptance_policy import GATE_NAMES, evaluate_policy


class CouncilService:
    """Coordinate role responses and preserve every candidate attempt."""

    def __init__(self, roles: Mapping[str, Callable[..., Any]], review_store: Any,
                 example_registry: Any, max_attempts: int = 3):
        """Bind exactly five injected roles and durable stores for a bounded run.

        ``roles`` are narada, shandilya, researcher, sutrakar, validator callables;
        ``max_attempts`` counts candidate compositions. ValueError rejects missing
        roles or unsafe retry bounds. Inspect role keys and attempt records when
        debugging; no external calls occur during construction.
        """
        required = {"narada", "shandilya", "researcher", "sutrakar", "validator"}
        if set(roles) != required or not 1 <= max_attempts <= 10:
            raise ValueError("Exactly five roles and 1-10 bounded attempts required")
        self.roles = roles
        self.review_store = review_store
        self.example_registry = example_registry
        self.max_attempts = max_attempts

    def run_unit(self, unit_id: str, narada: Dict[str, Any],
                 candidates: List[Dict[str, Any]], passages: List[Dict[str, Any]],
                 existing_sutras: Iterable[str] = (), run_id: str | None = None) -> Dict[str, Any]:
        """Run source analysis, arbitration, research, composition and validation.

        Inputs are one unit, source candidate records, verified passage packet and
        existing canon. Returns AI review eligibility or explicit blocked/rejected
        outcome with persisted attempt versions. Role failures propagate after a
        draft exists; missing sources block before calls. Inspect attempt issues,
        role error and stored versions for diagnostics, not raw provider secrets.
        """
        if not unit_id or not narada.get("sanskrit") or not candidates or not passages:
            raise ValueError("Source identity, candidates and passages required")
        candidate_by_id = {str(item.get("sutra_no")): item for item in candidates
                           if isinstance(item, dict) and item.get("sutra_no") and item.get("sanskrit")}
        if len(candidate_by_id) != len(candidates):
            raise ValueError("Every Shandilya candidate needs a unique ID and source text")
        first_attempt = self.review_store.start_attempt(run_id, unit_id, self.max_attempts) if run_id else 1
        thesis = self.roles["narada"](narada)
        review = self.roles["shandilya"](thesis, candidates)
        feedback: Dict[str, Any] = {}
        history = []
        for attempt in range(first_attempt, self.max_attempts + 1):
            if run_id and attempt > first_attempt:
                self.review_store.start_attempt(run_id, unit_id, self.max_attempts)
            # The arbiter is reengaged on a rejected pair or material source finding.
            arbitration = self.roles["sutrakar"]("arbitrate", thesis, review, feedback)
            if not isinstance(arbitration, dict) or arbitration.get("accepted") is not True:
                feedback = {"pairing": "rejected", "reason": arbitration.get("reason") if isinstance(arbitration, dict) else "invalid arbitration"}
                review = self.roles["shandilya"](thesis, candidates, feedback)
                history.append({"attempt": attempt, "status": "PAIR_REJECTED", "feedback": feedback})
                continue
            chosen_id = str(arbitration.get("sutra_no", ""))
            if chosen_id not in candidate_by_id:
                raise ValueError("Sutrakar selected a Shandilya ID outside retrieved candidates")
            arbitration = {**arbitration, "selected_shandilya": candidate_by_id[chosen_id]}
            research = self.roles["researcher"](narada, arbitration, passages, feedback)
            if not isinstance(research, dict) or not research.get("bridge") or not research.get("findings"):
                raise ValueError("Independent research bridge and findings required")
            consultation = self.roles["sutrakar"]("consult", thesis, review, research, passages, feedback)
            if not isinstance(consultation, dict) or not consultation.get("findings") or not consultation.get("challenges"):
                raise ValueError("Sutrakar independent consultation and challenges required")
            challenged_research = self.roles["researcher"](
                narada, arbitration, passages, {"challenges": consultation["challenges"]})
            if not isinstance(challenged_research, dict) or not challenged_research.get("findings"):
                raise ValueError("Researcher must answer independent consultation challenges")
            research = {**research, "sutrakar_consultation": consultation,
                        "challenge_response": challenged_research}
            # Evidence is assembled before either model call, independent of the
            # draft returned by the author. Injected roles must put this context
            # into their actual request and may not infer it from model output.
            evidence_context = {"passages": passages, "selected_shandilya": candidate_by_id[chosen_id],
                                "bridge": research["bridge"],
                                "consultation": consultation, "challenge_response": challenged_research}
            draft = self.roles["sutrakar"]("compose", thesis, arbitration, research, feedback, evidence_context)
            if not isinstance(draft, dict):
                raise ValueError("Structured composition required")
            assessment = self.roles["validator"](draft, research, passages, feedback, evidence_context)
            if not isinstance(assessment, dict) or not isinstance(assessment.get("gates"), dict):
                raise ValueError("Structured verifier gate evidence required")
            report = evaluate_policy(draft, assessment["gates"], existing_sutras)
            version = self.review_store.save_draft(unit_id, draft, report)
            history.append({"attempt": attempt, "version": version,
                            "status": report["overall_status"], "issues": report["issues"]})
            if report["overall_status"] == "AI_VALIDATED_FOR_HUMAN_REVIEW":
                examples = draft.get("named_examples")
                if not isinstance(examples, list) or not examples:
                    feedback = {"example_diversity": "Named example inventory required"}
                    history[-1]["status"] = "EXAMPLE_REVIEW_REQUIRED"
                    history[-1]["issues"].append("Named example inventory required")
                else:
                    from src.orchestration.review_store import fingerprint
                    try:
                        self.example_registry.reserve(unit_id, examples, fingerprint(draft))
                    except ValueError as exc:
                        feedback = {"example_diversity": str(exc)}
                        history[-1]["status"] = "EXAMPLE_REVIEW_REQUIRED"
                        history[-1]["issues"].append(str(exc))
                    else:
                        self.review_store.mark_ai_validated(unit_id, version)
                        outcome = {"unit_id": unit_id, "status": "HUMAN_REVIEW_PENDING",
                                   "version": version, "history": history}
                        if run_id:
                            self.review_store.finish_run_unit(run_id, unit_id, outcome)
                        return outcome
            else:
                feedback = {"gates": report["gates"], "issues": report["issues"],
                            "verifier_findings": assessment.get("findings", [])}
            self.example_registry.release(unit_id)
            if feedback.get("gates", {}).get("narada_fidelity") == "FAIL":
                thesis = self.roles["narada"](narada, feedback)
            if feedback.get("gates", {}).get("shandilya_fidelity") == "FAIL":
                review = self.roles["shandilya"](thesis, candidates, feedback)
        outcome = {"unit_id": unit_id, "status": "PARTIAL_BLOCKED",
                   "history": history, "reason": "Revision limit reached without all fifteen gates"}
        if run_id:
            self.review_store.finish_run_unit(run_id, unit_id, outcome)
        return outcome
