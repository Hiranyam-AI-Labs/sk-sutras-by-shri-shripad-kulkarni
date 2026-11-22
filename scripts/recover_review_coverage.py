"""Explicit one-attempt GPT-4o review recovery under the existing production cap."""

import argparse
import json
from pathlib import Path

from scripts.calibrate_independent_validator import ValidatorRegistry
from scripts.run_research_book import WORK, RATES, MODELS, parse_object
from src.orchestration.independent_review import canonical_hash
from src.providers.dispatch import BudgetedDispatcher
from src.providers.openai_adapter import OpenAIAdapter


def run(review_key):
    """Recover one diagnosed review key; return audited outcome without composition.

    Uses only the OpenAI credential and frozen production limits. The recovery
    implementation verifies eligibility and reserves its sole attempt before
    calling the callback. Provider/grounding errors propagate without retry.
    Inspect the retained raw response and recovery row when debugging failures.
    """
    from src.orchestration.independent_review import recover_missing_decision_coverage
    credential = Path("C:/Users/LENOVO/Dropbox/Hiranyam AI Labs/SK_Udyog_Sutras/openai_key.txt")
    adapter = OpenAIAdapter(model_id="gpt-4o", api_key=credential.read_text(encoding="utf-8").strip(),
                            offline_mode=False, max_tokens=4096, timeout_seconds=240.)
    dispatcher = BudgetedDispatcher(ValidatorRegistry(adapter), RATES, 50.891999, 3000,
                                   WORK / "dispatch.db", "full-book-v26", 172800,
                                   {role: 240. for role, _ in MODELS.values()})
    dispatcher.preflight_roles(["independent_validator"])

    def call(system, prompt):
        """Call only GPT-4o once and preserve its raw text before parsing.

        Return parsed JSON; reject truncation or model drift without retry.
        The dispatcher records reservations in the existing production ledger.
        """
        response = dispatcher.call("independent_validator", prompt, system,
                                   max_output_tokens=3000, allow_truncated=True)
        if response.provider != "openai" or response.model_id != "gpt-4o":
            raise RuntimeError("Coverage recovery model changed")
        raw = WORK / "responses" / f"coverage-recovery-{canonical_hash(response.content)}.txt"
        raw.write_text(response.content, encoding="utf-8")
        if response.was_truncated:
            raise RuntimeError("Coverage recovery truncated; no retry")
        return parse_object(response.content)

    return recover_missing_decision_coverage(WORK / "independent_review_v2.db", review_key, call)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-key", required=True)
    args = parser.parse_args()
    result = run(args.review_key)
    print(json.dumps(result, ensure_ascii=False, indent=2))
