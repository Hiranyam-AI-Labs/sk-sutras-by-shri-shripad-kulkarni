"""Offline structural fixtures only: no new sutras or real case-fact claims."""
from contextlib import redirect_stdout
from copy import deepcopy
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("prepare_source_first_book", ROOT / "scripts/prepare_source_first_book.py")
book = importlib.util.module_from_spec(spec)
spec.loader.exec_module(book)
from src.orchestration.research_council import _source_pair_ids
from src.orchestration.source_first_research import prepare_research_batch, validate_research_selection

PROSE = "मूळ स्रोत अर्थ संदर्भ मर्यादा विचार कृती संबंध स्पष्ट स्वतंत्र ठेवले आहेत"
QUOTE = "कर्मण्येवाधिकारस्ते मा फलेषु कदाचन ।"
PAIR_IDS = ["N002-S002", "N003-S002", "N004-S002"]


def seal(plan):
    plan["plan_sha256"] = book.digest({k: v for k, v in plan.items() if k != "plan_sha256"})


def bundle(plan, index, statuses=None, verdicts=None):
    name = f"research-{index:03d}"
    candidates = [c for c in plan["candidates"] if c["id"] in plan["batches"][index - 1]]
    evidence = [{**deepcopy(r), "id": c["id"] + "::" + r["source_id"], "candidate_id": c["id"]}
                for c in candidates for r in plan["library"]]
    request = prepare_research_batch(name, candidates, evidence, plan["source_hashes"])
    assessments, reviews = [], []
    for c in candidates:
        ident = c["id"]
        status = (statuses or {}).get(ident, "SUPPORTED")
        verdict = (verdicts or {}).get(ident, "PASS")
        assessments.append({"candidate_id": ident, "status": status,
            "evidence_ids": [ident + "::EVC-TEST"] if status == "SUPPORTED" else [],
            "relation_kind": "PARTIAL_OVERLAP", "source_core_mr": {"narada_mr": "नारद " + PROSE, "shandilya_mr": "शांडिल्य " + PROSE},
            "relation_mr": "संबंध " + PROSE, "limitations_mr": "मर्यादा " + PROSE, "business_extension_mr": "व्यवसाय " + PROSE})
        reviews.append({"candidate_id": ident, "verdict": verdict,
                        "issues_mr": [] if verdict == "PASS" else [PROSE]})
    selection = validate_research_selection(request, {
        **{k: request[k] for k in ("batch_id", "request_sha256", "source_hashes")},
        "assessments": assessments})
    gate = {"status": "EVIDENCE_SCREENED", "request_sha256": request["request_sha256"],
            "selection_sha256": book.digest(selection), "review": reviews,
            "supported_and_reviewed": [r["candidate_id"] for r, v in zip(assessments, reviews)
                                       if r["status"] == "SUPPORTED" and v["verdict"] == "PASS"],
            "held_for_review": [v["candidate_id"] for v in reviews if v["verdict"] != "PASS"],
            "author_approval": "PENDING", "new_sutras": 0}
    return {"request": request, "selection": selection, "gate": gate}


def fixture():
    # Source quotes are existing ancient text fragments, not generated formulas.
    nr = [{"id": n, "sanskrit": "सा त्वस्मिन् परप्रेमरूपा ॥", "meaning_mr": PROSE,
           "context_mr": PROSE, "source_note": "Synthetic structural fixture; not an edition certificate."}
          for n in (2, 3, 4)]
    sr = {"id": 2, "sanskrit": "सा परानुरक्तिरीश्वरे ॥२॥", "meaning_mr": PROSE, "context_mr": PROSE}
    hashes = {"narada": "a" * 64, "shandilya": "b" * 64, "EVC-TEST": "c" * 64}
    candidates = [{"id": ident, "narada": deepcopy(n), "shandilya": deepcopy(sr),
        "source_hashes": {k: hashes[k] for k in ("narada", "shandilya")},
        "scores": {"meaning": 35, "proposition": 20, "context": 15, "conditions": 10},
        "total": 80, "blockers": [], "failed_primary_minima": []} for ident, n in zip(PAIR_IDS, nr)]
    library = [{"source_id": "EVC-TEST", "source_sha256": hashes["EVC-TEST"],
                "location": "2.47 excerpt", "canonical_passage": QUOTE,
                "passage_sha256": book.byte_hash(QUOTE.encode()), "title": "Bhagavad Gita",
                "meaning_mr": PROSE, "context_mr": PROSE, "eligible": True, "verified": True,
                "source_record": {"author": "Traditionally attributed to Vyasa",
                                  "primary_url": "https://example.org/edition"}}]
    plan = {"candidate_count": 3, "reference_count": 1, "candidates": candidates,
            "library": library, "source_hashes": hashes, "batches": [PAIR_IDS[:2], PAIR_IDS[2:]]}
    seal(plan)
    screening = {f"research-{i:03d}": bundle(plan, i) for i in (1, 2)}
    refs = {}
    for prefix, records in (("N", nr), ("S", [sr])):
        for source in records:
            ident = prefix + str(source["id"])
            refs[ident] = {"id": ident, "title": "Frozen source fixture", "author": "Traditional attribution",
                           "locator": ident, "original_text": source["sanskrit"], "meaning_mr": source["meaning_mr"],
                           "url": "https://example.org/frozen-source", "tradition": "Indian"}
    cases = []
    for ident, kind, entity in (("positive-a", "positive", "Apple"),
                               ("caution-b", "caution", "Fixture B"),
                               ("positive-c", "positive", "Pixar"),
                               ("caution-d", "caution", "Fixture D"),
                               ("positive-e", "positive", "Fixture E")):
        cases.append({"case_id": ident, "canonical_case_id": ident, "kind": kind,
                      "entity": entity, "text_mr": "चाचणीपुरता मजकूर ऐतिहासिक तथ्याचा दावा नाही",
                      "recorded_fact": "Synthetic test fixture only; not a historical fact.",
                      "url": "https://example.org/case", "source_title": "Fixture",
                      "new_book_status": "UNALLOCATED_RESEARCH_INVENTORY", "flags": [],
                      "entity_identity": {"normalized_entity_key": book.normalized(entity),
                                          "deduplication_keys": [book.normalized(entity)],
                                          "recorded_aliases_and_related_labels": []}})
    pool = {"case_count": len(cases), "cases": cases}
    overlay = {"fact_verifications": [], "identity_verifications": [], "cross_case_relationships": []}
    for case in cases:
        overlay["fact_verifications"].append({"case_id": case["case_id"], "status": "MATCH",
            "case_pool_record_sha256": book.digest(case),
            "existing_text_mr_sha256": book.byte_hash(case["text_mr"].encode()),
            "existing_recorded_fact_sha256": book.byte_hash(case["recorded_fact"].encode()),
            "existing_marathi_material_fact_contradiction_found": False,
            "use_condition": "Fixture only; preserve limits."})
    return dict(stage_plan=plan, screening=screening, case_pool=pool,
                verification_overlay=overlay, pair_references=refs, ordered_selection_cards=[card()])


def card(pair=PAIR_IDS[0], suffix="", stage="opening", positive="positive-a", caution="caution-b"):
    return {"card_id": "card" + suffix, "cluster_id": "cluster" + suffix,
            "representative_pair_id": pair, "alternative_pairs": [],
            "topic_mr": "निष्ठा" + suffix, "decision_mr": "निर्णय" + suffix,
            "action_mr": "कृती" + suffix, "source_derivation_mr": PROSE,
            "cluster_rationale_mr": PROSE, "journey_stage": stage, "ordering_reason_mr": PROSE,
            "selection_provenance": {"curator": "Test curator", "rationale_mr": PROSE},
            "case_slots": [{"kind": "positive", "case_id": positive, "fit_reason_mr": PROSE, "limitations_mr": PROSE},
                           {"kind": "caution", "case_id": caution, "fit_reason_mr": PROSE, "limitations_mr": PROSE}]}


class BookPlanTests(unittest.TestCase):
    def setUp(self):
        self.args = fixture()

    def prepare(self):
        return book.prepare_book_plan(**self.args)

    def refresh_case_binding(self, ident):
        case = next(c for c in self.args["case_pool"]["cases"] if c["case_id"] == ident)
        for check in self.args["verification_overlay"]["fact_verifications"]:
            if check["case_id"] == ident:
                check["case_pool_record_sha256"] = book.digest(case)

    def test_complete_draft_exact_canonical_packet_and_council_interface(self):
        before = deepcopy(self.args)
        result = self.prepare()
        self.assertEqual(result["status"], "DRAFT")
        self.assertEqual(result["new_sutras"], 0)
        self.assertFalse(result["publication_approved"])
        packet = result["entries"][0]["source_packet"]
        self.assertEqual(packet["pair_reference_ids"], ["N2", "S2"])
        self.assertEqual(_source_pair_ids(packet)[0], {"N2", "S2"})
        for ref in packet["references"]:
            self.assertEqual(set(ref), set(book.REFERENCE_FIELDS))
        self.assertEqual(packet["references"][2]["original_text"], QUOTE)
        self.assertEqual(packet["source_contexts"]["N2"]["context_mr"], PROSE)
        self.assertEqual(packet["examples"][0]["text_mr"], self.args["case_pool"]["cases"][0]["text_mr"])
        self.assertEqual(result["council_payload"]["briefs"][0]["number"], 1)
        self.assertEqual(self.args, before)

    def test_missing_batch_blocks_any_draft(self):
        del self.args["screening"]["research-002"]
        coverage = book.research_coverage(self.args["stage_plan"], self.args["screening"])
        self.assertEqual(coverage["status"], "INCOMPLETE")
        self.assertEqual(coverage["missing_batches"], ["research-002"])
        with self.assertRaisesRegex(ValueError, "coverage incomplete"):
            self.prepare()

    def test_complete_pending_dispositions_exclude_pairs_without_blocking_eligible(self):
        self.args["screening"]["research-002"] = bundle(self.args["stage_plan"], 2, {PAIR_IDS[2]: "PENDING"})
        result = self.prepare()
        self.assertEqual(result["status"], "DRAFT")
        self.assertEqual(result["research_coverage"]["status"], "COMPLETE")
        self.assertEqual(result["research_coverage"]["pending_pair_ids"], [PAIR_IDS[2]])
        self.assertNotIn(PAIR_IDS[2], result["unselected_eligible_pair_ids"])
        self.args["ordered_selection_cards"][0]["representative_pair_id"] = PAIR_IDS[2]
        with self.assertRaisesRegex(ValueError, "SUPPORTED and independent PASS"):
            self.prepare()

    def test_pending_alternative_excluded_and_missing_batch_still_blocks(self):
        self.args["screening"]["research-001"] = bundle(self.args["stage_plan"], 1, {PAIR_IDS[1]: "PENDING"})
        self.args["ordered_selection_cards"][0]["alternative_pairs"] = [{
            "pair_id": PAIR_IDS[1], "same_decision_action_reason_mr": PROSE}]
        with self.assertRaisesRegex(ValueError, "SUPPORTED and independent PASS"):
            self.prepare()
        del self.args["screening"]["research-002"]
        self.args["ordered_selection_cards"][0]["alternative_pairs"] = []
        with self.assertRaisesRegex(ValueError, "missing batches"):
            self.prepare()

    def test_all_pending_is_complete_coverage_with_no_eligible_candidates(self):
        for n in (1, 2):
            self.args["screening"][f"research-{n:03d}"] = bundle(
                self.args["stage_plan"], n, {i: "PENDING" for i in PAIR_IDS})
        self.args["ordered_selection_cards"] = []
        result = self.prepare()
        self.assertEqual(result["research_coverage"]["status"], "COMPLETE")
        self.assertEqual(result["entries"], [])
        self.assertEqual(result["unselected_eligible_pair_ids"], [])
        self.assertEqual(set(result["research_coverage"]["pending_pair_ids"]), set(PAIR_IDS))

    def test_supported_and_independent_pass_are_both_required(self):
        for status, verdict in (("UNSUPPORTED", "PASS"), ("SUPPORTED", "REVIEW_REQUIRED")):
            with self.subTest(status=status, verdict=verdict):
                self.args = fixture()
                self.args["screening"]["research-001"] = bundle(self.args["stage_plan"], 1,
                    {PAIR_IDS[0]: status}, {PAIR_IDS[0]: verdict})
                with self.assertRaisesRegex(ValueError, "SUPPORTED and independent PASS"):
                    self.prepare()

    def test_stale_plan_request_selection_and_gate_fail_closed(self):
        for target in ("plan", "request", "selection", "gate"):
            with self.subTest(target=target):
                self.args = fixture()
                batch = self.args["screening"]["research-001"]
                if target == "plan":
                    self.args["stage_plan"]["candidates"][0]["narada"]["context_mr"] += " drift"
                elif target == "request":
                    batch["request"]["candidates"][0]["narada"]["context_mr"] += " drift"
                elif target == "selection":
                    batch["selection"]["assessments"][0]["selected_evidence"][0]["canonical_passage"] += " drift"
                    batch["gate"]["selection_sha256"] = book.digest(batch["selection"])
                else:
                    batch["gate"]["selection_sha256"] = "0" * 64
                with self.assertRaises(ValueError):
                    self.prepare()

    def test_gate_cannot_invent_supported_or_independent_pass(self):
        self.args["screening"]["research-001"]["gate"]["supported_and_reviewed"] = []
        with self.assertRaisesRegex(ValueError, "ledger drift"):
            self.prepare()

    def test_scalar_ids_and_duplicate_batch_partition_rejected(self):
        for invalid in (True, [2], "2", 2.0, 85):
            self.args = fixture()
            self.args["stage_plan"]["candidates"][0]["narada"]["id"] = invalid
            seal(self.args["stage_plan"])
            with self.assertRaises(ValueError):
                self.prepare()
        self.args = fixture()
        self.args["stage_plan"]["batches"][1] = [PAIR_IDS[0]]
        seal(self.args["stage_plan"])
        with self.assertRaisesRegex(ValueError, "partition"):
            self.prepare()

    def test_primary_component_minima_and_blockers_cannot_be_bypassed(self):
        for field in ("scores", "blockers"):
            self.args = fixture()
            candidate = self.args["stage_plan"]["candidates"][0]
            if field == "scores":
                candidate["scores"]["meaning"] = 29.5
                candidate["total"] = sum(candidate["scores"].values())
            else:
                candidate["blockers"] = ["forced_connection"]
            seal(self.args["stage_plan"])
            with self.assertRaises(ValueError):
                bundle(self.args["stage_plan"], 1)

    def test_both_canonical_pair_references_mandatory_and_exact(self):
        for key in ("N2", "S2"):
            self.args = fixture()
            del self.args["pair_references"][key]
            with self.assertRaisesRegex(ValueError, "mandatory canonical"):
                self.prepare()
        self.args = fixture()
        self.args["pair_references"]["S2"]["original_text"] += " drift"
        with self.assertRaisesRegex(ValueError, "quote/meaning drift"):
            self.prepare()
        self.args = fixture()
        self.args["pair_references"]["N2"]["extra"] = "regenerated quote"
        with self.assertRaisesRegex(ValueError, "eight reference fields"):
            self.prepare()

    def test_declared_cluster_merges_keep_alternative_pair_provenance(self):
        c = self.args["ordered_selection_cards"][0]
        c["alternative_pairs"] = [{"pair_id": PAIR_IDS[1], "same_decision_action_reason_mr": PROSE}]
        result = self.prepare()
        alt = result["entries"][0]["source_packet"]["selection_provenance"]["alternative_pairs"][0]
        self.assertEqual(alt["pair_id"], PAIR_IDS[1])
        self.assertEqual(alt["research_provenance"]["independent_review"]["verdict"], "PASS")
        self.assertEqual(result["unselected_eligible_pair_ids"], [PAIR_IDS[2]])

    def test_duplicate_clusters_literal_decisions_and_pair_reuse_rejected(self):
        for mode in ("cluster", "decision", "pair"):
            self.args = fixture()
            second = card(PAIR_IDS[1], "2", "practice", "positive-c", "caution-d")
            if mode == "cluster":
                second["cluster_id"] = "cluster"
            elif mode == "decision":
                second["decision_mr"] = "निर्णय"
                second["action_mr"] = "कृती"
            else:
                second["representative_pair_id"] = PAIR_IDS[0]
            self.args["ordered_selection_cards"].append(second)
            with self.assertRaises(ValueError):
                self.prepare()

    def test_explicit_journey_order_preserved_and_reverse_rejected(self):
        self.args["ordered_selection_cards"].append(card(PAIR_IDS[1], "2", "closure", "positive-c", "caution-d"))
        result = self.prepare()
        self.assertEqual([e["brief"]["journey_stage"] for e in result["entries"]], ["opening", "closure"])
        self.args["ordered_selection_cards"][0]["journey_stage"] = "closure"
        self.args["ordered_selection_cards"][1]["journey_stage"] = "practice"
        with self.assertRaisesRegex(ValueError, "reverse"):
            self.prepare()

    def test_no_fit_stays_unassigned_and_is_not_council_ready(self):
        self.args["ordered_selection_cards"][0]["case_slots"][0] = {
            "kind": "positive", "case_id": None, "unassigned_reason_mr": "No defensible fit curated."}
        result = self.prepare()
        self.assertEqual(result["entries"][0]["case_assignments"][0]["status"], "UNASSIGNED")
        self.assertFalse(result["entries"][0]["council_ready"])
        self.assertEqual(result["council_payload"]["briefs"], [])

    def test_unknown_cases_missing_fit_and_rewritten_fact_fields_rejected(self):
        for mode in ("unknown", "reason", "facts", "order"):
            self.args = fixture()
            slots = self.args["ordered_selection_cards"][0]["case_slots"]
            if mode == "unknown": slots[0]["case_id"] = "invented"
            elif mode == "reason": slots[0]["fit_reason_mr"] = ""
            elif mode == "facts": slots[0]["recorded_fact"] = "invented fact"
            else: slots.reverse()
            with self.assertRaises(ValueError):
                self.prepare()

    def test_hold_unverified_and_identity_only_do_not_qualify_case_facts(self):
        for mode in ("hold", "unverified", "identity", "pool_hold"):
            self.args = fixture()
            overlay = self.args["verification_overlay"]
            check = overlay["fact_verifications"][0]
            if mode == "hold": check["status"] = "HOLD"
            elif mode in ("unverified", "identity"):
                overlay["fact_verifications"].pop(0)
                if mode == "identity":
                    overlay["identity_verifications"] = [{"case_id": "positive-a", "status": "MATCH",
                        "case_pool_record_sha256": check["case_pool_record_sha256"], "verified_relationships": []}]
            else:
                self.args["case_pool"]["cases"][0]["flags"].append("HOLD_FACTS")
                self.refresh_case_binding("positive-a")
            result = self.prepare()
            self.assertEqual(result["entries"][0]["case_assignments"][0]["status"], "UNASSIGNED")

    def test_qualified_case_keeps_exact_fact_and_full_qualification(self):
        check = self.args["verification_overlay"]["fact_verifications"][0]
        check["status"] = "QUALIFIED"
        check["use_condition"] = "Preserve exact access limit."
        result = self.prepare()
        slot = result["entries"][0]["case_assignments"][0]
        self.assertEqual(slot["verification"], check)
        self.assertEqual(slot["canonical_case"], self.args["case_pool"]["cases"][0])

    def test_alias_canonical_case_and_apple_pixar_jobs_conflicts_excluded(self):
        for mode in ("alias", "canonical", "jobs"):
            self.args = fixture()
            self.args["ordered_selection_cards"].append(card(PAIR_IDS[1], "2", "people", "positive-c", "caution-d"))
            a, c = self.args["case_pool"]["cases"][0], self.args["case_pool"]["cases"][2]
            if mode == "alias":
                c["entity_identity"]["recorded_aliases_and_related_labels"] = ["APPLE"]
                self.refresh_case_binding("positive-c")
            elif mode == "canonical":
                c["canonical_case_id"] = a["canonical_case_id"]
                self.refresh_case_binding("positive-c")
            else:
                self.args["verification_overlay"]["cross_case_relationships"] = [{
                    "case_ids": ["positive-a", "positive-c"], "person": "Steve Jobs",
                    "relationship": "SHARED_HISTORICAL_LEADER",
                    "case_record_bindings": {r["case_id"]: book.digest(r) for r in (a, c)}}]
            with self.assertRaisesRegex(ValueError, "repeated case/person"):
                self.prepare()

    def test_overlay_record_and_existing_fact_hash_drift_rejected(self):
        for mode in ("case", "hash"):
            self.args = fixture()
            if mode == "case": self.args["case_pool"]["cases"][0]["recorded_fact"] += " drift"
            else: self.args["verification_overlay"]["fact_verifications"][0]["existing_text_mr_sha256"] = "0" * 64
            with self.assertRaisesRegex(ValueError, "hash drift"):
                self.prepare()

    def test_no_quota_empty_explicit_selection_is_a_valid_empty_draft(self):
        self.args["ordered_selection_cards"] = []
        result = self.prepare()
        self.assertEqual(result["entries"], [])
        self.assertEqual(len(result["unselected_eligible_pair_ids"]), 3)

    def test_cli_incomplete_does_not_write_or_require_selection_cards(self):
        self.args["screening"].pop("research-002")
        inputs = {k: v for k, v in self.args.items() if k not in ("ordered_selection_cards", "pair_references")}
        with tempfile.TemporaryDirectory(prefix="test-source-first-book-") as temp:
            target = Path(temp).resolve() / "plan.json"
            with patch.object(book, "load_inputs", return_value=inputs), redirect_stdout(io.StringIO()) as output:
                self.assertEqual(book.main(["--work", temp, "--output", str(target)]), 2)
            self.assertIn('"status": "INCOMPLETE"', output.getvalue())
            self.assertNotIn('"status": "DRAFT"', output.getvalue())
            self.assertFalse(target.exists())


    def test_alternative_pair_is_not_a_route_around_independent_review(self):
        self.args["screening"]["research-001"] = bundle(self.args["stage_plan"], 1,
                                                       verdicts={PAIR_IDS[1]: "REVIEW_REQUIRED"})
        self.args["ordered_selection_cards"][0]["alternative_pairs"] = [{
            "pair_id": PAIR_IDS[1], "same_decision_action_reason_mr": PROSE}]
        with self.assertRaisesRegex(ValueError, "SUPPORTED and independent PASS"):
            self.prepare()

    def test_identity_hold_excluded_even_when_case_fact_matches(self):
        case = self.args["case_pool"]["cases"][0]
        self.args["verification_overlay"]["identity_verifications"] = [{
            "case_id": case["case_id"], "status": "HOLD", "case_pool_record_sha256": book.digest(case),
            "verified_relationships": []}]
        result = self.prepare()
        self.assertEqual(result["entries"][0]["case_assignments"][0]["status"], "UNASSIGNED")

    def test_loader_rejects_source_file_and_whole_pool_byte_drift(self):
        with tempfile.TemporaryDirectory(prefix="test-source-first-book-") as temp:
            base = Path(temp).resolve()
            work = base / "task"
            work.mkdir()
            old = base / "20261119-sutra-comparison"
            old.mkdir()
            plan = self.args["stage_plan"]
            for name in ("narada", "shandilya"):
                raw = json.dumps([c[name] for c in plan["candidates"]], ensure_ascii=False).encode()
                (old / f"{name}-working.json").write_bytes(raw)
                plan["source_hashes"][name] = book.byte_hash(raw)
                for candidate in plan["candidates"]:
                    candidate["source_hashes"][name] = plan["source_hashes"][name]
            seal(plan)
            pool_raw = json.dumps(self.args["case_pool"], ensure_ascii=False).encode()
            overlay = deepcopy(self.args["verification_overlay"])
            overlay["input_bindings"] = [{"path": "logs/task/business-case-pool.json",
                                         "sha256": book.byte_hash(pool_raw), "bytes": len(pool_raw)}]
            (work / "business-case-pool.json").write_bytes(pool_raw)
            (work / "business-case-verification-overlay.json").write_text(json.dumps(overlay), encoding="utf-8")
            (work / "research-stage-plan.json").write_text(json.dumps(plan), encoding="utf-8")
            (work / "research-screening").mkdir()
            for n in (1, 2):
                for key, value in bundle(plan, n).items():
                    (work / "research-screening" / f"research-{n:03d}-{key}.json").write_text(
                        json.dumps(value), encoding="utf-8")
            inputs = book.load_inputs(work)
            self.assertEqual(book.research_coverage(inputs["stage_plan"], inputs["screening"])["status"], "COMPLETE")
            alternative_overlay = {**overlay, "test_optional_overlay": True}
            (work / "optional-overlay.json").write_text(json.dumps(alternative_overlay), encoding="utf-8")
            optional = book.load_inputs(work, case_overlay="optional-overlay.json")
            self.assertTrue(optional["verification_overlay"]["test_optional_overlay"])
            self.assertIn("optional-overlay.json", optional["input_provenance"])
            for path, message in ((old / "narada-working.json", "source file hash drift"),
                                  (work / "business-case-pool.json", "whole-pool byte binding")):
                original = path.read_bytes()
                path.write_bytes(original + b" ")
                try:
                    with self.assertRaisesRegex(ValueError, message):
                        book.load_inputs(work)
                finally:
                    path.write_bytes(original)

    def test_cli_never_overwrites_existing_or_protected_output(self):
        inputs = {k: v for k, v in self.args.items() if k not in ("ordered_selection_cards", "pair_references")}
        with tempfile.TemporaryDirectory(prefix="test-source-first-book-") as temp:
            work = Path(temp).resolve()
            target = work / "protected-opening.json"
            target.write_bytes(b"protected original bytes")
            cards, refs = work / "cards.json", work / "refs.json"
            cards.write_text(json.dumps(self.args["ordered_selection_cards"]), encoding="utf-8")
            refs.write_text(json.dumps(self.args["pair_references"]), encoding="utf-8")
            with patch.object(book, "load_inputs", return_value=inputs):
                with self.assertRaises(FileExistsError):
                    book.main(["--work", temp, "--cards", str(cards), "--pair-references", str(refs),
                               "--output", str(target)])
            self.assertEqual(target.read_bytes(), b"protected original bytes")


    def write_merge_fixture(self, directory):
        work = Path(directory).resolve()
        pool = self.args["case_pool"]
        def write(name, value):
            raw = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()
            (work / name).write_bytes(raw)
            return book.byte_hash(raw)
        pool_sha = write("business-case-pool.json", pool)
        original = deepcopy(self.args["verification_overlay"])
        original["fact_verifications"] = original["fact_verifications"][:1]
        identity_case = pool["cases"][1]
        original["identity_verifications"] = [{
            "case_id": identity_case["case_id"], "status": "HOLD",
            "case_pool_record_sha256": book.digest(identity_case), "verified_relationships": [],
            "reason": "Identity fixture remains unresolved; distinct from fact status."}]
        original["input_bindings"] = [{"path": "business-case-pool.json", "sha256": pool_sha}]
        original_sha = write("business-case-verification-overlay.json", original)
        for n in range(4):
            rows = []
            for i, case in enumerate(pool["cases"]):
                if i % 4 != n or i == 0:
                    continue
                rows.append({"case_id": case["case_id"], "canonicalcasehash": book.digest(case),
                             "status": {1: "QUALIFIED", 2: "HOLD"}.get(n, "MATCH"),
                             "primary_urls": ["https://example.org/fixture"],
                             "checked_date_local": "2026-11-21", "exact_supported_fact": "Synthetic proof fixture.",
                             "reason_mr": PROSE, "limitations_mr": "Fixture only; no real factual claim."})
            shard = {"status": "COMPLETE", "shard": n, "records": rows}
            if n == 0:
                shard.update(pool_sha256=pool_sha, overlay_sha256_at_selection=original_sha)
            elif n == 1:
                shard["input_bindings"] = {"pool_sha256": pool_sha, "overlay_sha256": original_sha}
            elif n == 2:
                shard["input_bindings"] = [{"path": "business-case-pool.json", "sha256": pool_sha},
                    {"path": "business-case-verification-overlay.json", "sha256": original_sha}]
            else:
                shard.update(pool_sha256=pool_sha, excluded_overlay_sha256=original_sha)
            write(f"business-case-fresh-shard-{n}.json", shard)
        return work, original

    def test_merge_preserves_original_proofs_and_separates_identity_holds(self):
        with tempfile.TemporaryDirectory(prefix="test-source-first-merge-") as temp:
            work, original = self.write_merge_fixture(temp)
            before = {p.name: p.read_bytes() for p in work.iterdir()}
            merged = book.prepare_complete_case_overlay(work)
            self.assertEqual(len(merged["fact_verifications"]), 5)
            self.assertEqual(merged["coverage"]["fact_dispositions"], {"MATCH": 3, "QUALIFIED": 1, "HOLD": 1})
            self.assertEqual(merged["fact_verifications"][0], original["fact_verifications"][0])
            self.assertEqual(merged["identity_verifications"], original["identity_verifications"])
            self.assertEqual(merged["cross_case_relationships"], original["cross_case_relationships"])
            self.assertEqual(merged["coverage"]["identity_hold_case_ids"], ["caution-b"])
            self.assertEqual(merged["coverage"]["fact_hold_case_ids"], ["positive-c"])
            self.assertEqual(merged["proof_artifacts"][0]["document"], original)
            raw = merged["proof_artifacts"][1]["document"]["records"][0]
            fresh = next(r for r in merged["fact_verifications"] if r["case_id"] == raw["case_id"])
            for key, value in raw.items():
                self.assertEqual(fresh[key], value)
            self.assertNotIn("existing_marathi_material_fact_contradiction_found", fresh)
            self.assertEqual(len(fresh["merge_provenance"]["structurally_added_binding_fields"]), 3)
            self.assertEqual(before, {p.name: p.read_bytes() for p in work.iterdir()})

    def test_merge_rejects_missing_duplicate_foreign_wrong_shard_and_hash_drift(self):
        for mode in ("missing", "duplicate", "foreign", "wrong_shard", "pool_binding", "record_hash", "text_hash"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory(prefix="test-source-first-merge-") as temp:
                work, _ = self.write_merge_fixture(temp)
                path = work / "business-case-fresh-shard-1.json"
                shard = json.loads(path.read_text(encoding="utf-8"))
                if mode == "missing": shard["records"] = []
                elif mode == "duplicate": shard["records"].append(deepcopy(shard["records"][0]))
                elif mode == "foreign": shard["records"][0]["case_id"] = "foreign"
                elif mode == "wrong_shard": shard["shard"] = 3
                elif mode == "pool_binding": shard["input_bindings"]["pool_sha256"] = "0" * 64
                elif mode == "record_hash": shard["records"][0]["canonicalcasehash"] = "0" * 64
                else: shard["records"][0]["existing_text_mr_sha256"] = "0" * 64
                path.write_text(json.dumps(shard), encoding="utf-8")
                with self.assertRaises(ValueError):
                    book.prepare_complete_case_overlay(work)

    def test_merge_new_output_never_overwrites_original_or_previous_release(self):
        with tempfile.TemporaryDirectory(prefix="test-source-first-merge-") as temp:
            work, _ = self.write_merge_fixture(temp)
            original_path = work / "business-case-verification-overlay.json"
            original_bytes = original_path.read_bytes()
            with redirect_stdout(io.StringIO()):
                self.assertEqual(book.main(["--work", str(work), "--merge-case-overlay"]), 0)
                with self.assertRaises(FileExistsError):
                    book.main(["--work", str(work), "--merge-case-overlay"])
                with self.assertRaises(FileExistsError):
                    book.main(["--work", str(work), "--merge-case-overlay", "--output", str(original_path)])
            self.assertEqual(original_path.read_bytes(), original_bytes)

    def test_absent_legacy_boolean_is_not_invented_and_explicit_contradiction_still_holds(self):
        fact = self.args["verification_overlay"]["fact_verifications"][0]
        del fact["existing_marathi_material_fact_contradiction_found"]
        result = self.prepare()
        self.assertEqual(result["entries"][0]["case_assignments"][0]["status"], "DRAFT_ASSIGNED")
        self.assertNotIn("existing_marathi_material_fact_contradiction_found",
                         result["entries"][0]["case_assignments"][0]["verification"])
        fact["existing_marathi_material_fact_contradiction_found"] = True
        self.assertEqual(self.prepare()["entries"][0]["case_assignments"][0]["status"], "UNASSIGNED")


    def test_optional_complete_overlay_load_replays_original_proofs_and_rejects_tampering(self):
        with tempfile.TemporaryDirectory(prefix="test-source-first-merge-load-") as temp:
            base = Path(temp).resolve()
            work = base / "task"
            work.mkdir()
            self.write_merge_fixture(work)
            frozen_sources = base / "20261119-sutra-comparison"
            frozen_sources.mkdir()
            plan = self.args["stage_plan"]
            for name in ("narada", "shandilya"):
                raw = json.dumps([c[name] for c in plan["candidates"]]).encode()
                (frozen_sources / f"{name}-working.json").write_bytes(raw)
                plan["source_hashes"][name] = book.byte_hash(raw)
                for candidate in plan["candidates"]:
                    candidate["source_hashes"][name] = plan["source_hashes"][name]
            seal(plan)
            (work / "research-stage-plan.json").write_text(json.dumps(plan), encoding="utf-8")
            (work / "research-screening").mkdir()
            for n in (1, 2):
                for key, value in bundle(plan, n).items():
                    (work / "research-screening" / f"research-{n:03d}-{key}.json").write_text(
                        json.dumps(value), encoding="utf-8")
            merged = book.prepare_complete_case_overlay(work)
            output = work / "complete.json"
            output.write_text(json.dumps(merged), encoding="utf-8")
            inputs = book.load_inputs(work, case_overlay="complete.json")
            self.assertEqual(inputs["verification_overlay"], merged)
            self.assertEqual(book.research_coverage(inputs["stage_plan"], inputs["screening"])["status"], "COMPLETE")
            merged["fact_verifications"][1]["exact_supported_fact"] += " tampered"
            output.write_text(json.dumps(merged), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "merged overlay/proof artifact drift"):
                book.load_inputs(work, case_overlay=output)

    def test_current_complete_overlay_has_exact_expected_fact_counts(self):
        merged = book.prepare_complete_case_overlay()
        self.assertEqual(merged["coverage"]["fact_records"], 200)
        self.assertEqual(merged["coverage"]["fact_dispositions"], {"MATCH": 167, "QUALIFIED": 30, "HOLD": 3})
        self.assertEqual(merged["coverage"]["identity_dispositions"]["HOLD"], 1)
        self.assertEqual(len(merged["proof_artifacts"]), 5)

    def test_live_frozen_inputs_are_read_only_and_current_gates_replay(self):
        inputs = book.load_inputs()
        coverage = book.research_coverage(inputs["stage_plan"], inputs["screening"])
        self.assertEqual(coverage["expected_pairs"], inputs["stage_plan"]["candidate_count"])
        self.assertLessEqual(coverage["completed_batches"], coverage["expected_batches"])
        for name, fp in inputs["input_provenance"].items():
            self.assertEqual(book.byte_hash((book.WORK / name).read_bytes()), fp["sha256"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
