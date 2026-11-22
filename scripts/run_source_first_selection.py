"""Exhaustive source-only arbitration; no composition, cases, export or publication.

API: load_selection_inputs(input_dir), build_selection(stage_plan, screening,
pair_references), code_bindings(), offline_quality_metadata(), preflight(...),
run(..., registry=offline_fake). CLI is read-only preflight unless --live;
--live requires explicit credentials, exact offline receipt and calibration.
Execution test receipts are append-only per invocation, outside immutable provider
cache identity. Every invocation still requires the CURRENT exact-code gate.
--resume replays frozen batches and successful stage caches without new calls.
--pilot-pair-id optionally stable-moves one eligible pair to the singleton,
retaining every other pair and its relative order before run-local numbering.
Policy v2 uses fresh run bindings; v1 caches/artifacts are never resumed.
--target starts batches whose first logical number <= target: an entered batch
is always completed in full. Numbers are candidate identities, not book order.

The parent supplies the offline receipt (never self-certified here): PASS,
paid_calls=0, code_sha256=code_bindings(), tests=[{path,passed>0,failed:0,errors:0}]
for every REQUIRED_TESTS. Calibration is the existing exact validator calibration,
although this runner never calls the fifth role. Fixed reservation caps must cover
all batch stages. Accepted metadata are Sutrakar judgments, not offline guesses.

Optional input: source-selection-supplement-menu.json activates the fixed
marathi-bhakti-supplement-verified.json and source-selection-supplement-menu-review.json
triplet. Pending/missing review fails closed; no menu means identical baseline.
Exact raw proofs are embedded only in mapped packets and never sent as proof
inventories to models. rebuild_source_packet validates saved pre-case packets
without reopening research; caller retains the original discussion hash gate.
An explicit source-selection-reference-menu-v2 applies only to wholly unstarted
92+ batches. Saved v1 policies/requests remain v1 on resume, even when v2 is
requested for later batches. Both versions keep the same roles/caps and gates.
"""
from copy import deepcopy
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts import prepare_source_first_book as preparation
from scripts import run_source_first_book as book
from src.orchestration.research_council import ResearchCouncil, VOICES
from src.orchestration.source_first_provider import (
    SourceFirstProvider, SourceFirstStopped, create_live_provider, call_with_lossless_framing, _exclusive, _work_path,
)
from src.orchestration.source_first_writing import (
    WRITING_SYSTEM, writing_contract, writing_view, require_proposal_support,
)

MODELS, PROVIDERS, RATES = book.MODELS, book.PROVIDERS, book.RATES
load, save, byte_hash = book.load, book.save, book.byte_hash
require_validator_calibration = book.require_validator_calibration
REQUIRED_TESTS = tuple(dict.fromkeys((*book.REQUIRED_TESTS,
    'tests/test_source_first_selection_runner.py', 'tests/test_source_first_stage.py',
    'tests/test_source_first_research.py', 'tests/test_source_first_research_runner.py',
    'tests/test_research_acceptance.py', 'tests/test_validator_calibration_cases.py',
    'tests/test_dispatch.py', 'tests/test_research_spend_guard.py', 'tests/test_providers.py',
    'tests/test_source_first_partial_completion.py',
    'tests/test_source_first_partial_completion_runner.py',
    'tests/test_source_first_evidence_anchor.py', 'tests/test_source_peer_evidence.py',
    'tests/test_source_peer_reference_v2.py', 'tests/test_source_first_proposal_recovery.py')))
POLICY = {'version': 'source-only-selection-v2', 'pilot_size': 1, 'batch_size': 10,
          'discussion_effort': 'low', 'timeout_seconds': 240,
          'minimum_tokens': 4096, 'tokens_per_entry': 900,
          'journey_stages': list(preparation.JOURNEY), 'composition': False,
          'json_framing': 'single-extra-closing-brace-v1', 'evidence_quarantine': False}
ROLE_FOCUS = {
    'narada': 'Explain your own canonical Narada sutra, original meaning, context and limits. Challenge the other three voices using that source; do not self-final-approve an application.',
    'shandilya': 'Explain your own canonical Shandilya sutra, original meaning, context and limits. Challenge the other three voices using that source; do not self-final-approve an application.',
    'researcher': 'Support, complement or qualify the relationship using ONLY supplied verified supplementary passages. Explain what they support and what they do not; they need not repeat the pair definition or mention business. Preserve original meaning and limits, do not invent citations, and do not claim supplementary proof from the sutra pair alone.',
    'sutrakar': 'Compare and challenge all three source voices. Own the constructive synthesis: refine or replace the initial researcher hypothesis yourself when generic. After ALL replies, explicitly assess the strongest bounded peer response, adopting, refining or rejecting it with a source-specific reason. Supply the accepted business decision/action and short formula yourself; do not delegate that responsibility to the source specialists. Reject forced or empty bridges without a formula.',
}
SELECTION_SYSTEM = WRITING_SYSTEM + """
SOURCE-ONLY SELECTION: no long composition, cases, exports or author approval.
All four voices must read peer positions, directed challenges and replies as
available at that stage. Preserve original source meanings and qualifications.
Never equate God with profit or immortality with corporate longevity. Business
extensions are qualified interpretations, not statements by ancient authors.
Reject genuinely the same practical business decision/action as prior accepted
items only when their status is ACCEPTED_FOR_CASE_ASSIGNMENT (Sutrakar ACCEPT
plus all three peer PASS). held_selection_decisions are unresolved, NOT accepted
chapters: they do not consume a practical decision or block a genuinely better
supported candidate for the same idea. Keep their issues for later diagnosis;
prior_formulas may still exclude their literal formula. shared broad source concepts alone do NOT establish duplication. Within
this batch compare candidates as well: no acceptance quota, no forced merge.
Separate original devotional proposition, the supplied supplementary relation,
and a qualified modern application. A supplement may support, complement or
qualify a feature without repeating the same definition or mentioning business.
Absence of literal business language alone is not a veto. Preserve the source's
objects, antecedents and limits; calling something an analogy does not excuse
false attribution, a forced identity or an unsupported practical promise.
Sutrakar owns the synthesis and may replace a generic initial hypothesis: source
भाव -> transferable human disposition -> bounded professional action with actor,
trigger, limit and observable next step. Source specialists test meanings and
limits; they are not required to write the final business decision. Assess the
strongest bounded response in the completed peer replies before final arbitration.
The author/source themes are legitimate inspiration, not a novelty veto.
literal_formula_exclusions forbids exact/normalized formula copying only, never
concepts. Only prior_accepted_decisions committed in THIS new book/run supplies
historical decision comparators; identify the comparator and materially same
condition/action before claiming duplication. Old author themes and held entries
do not constitute committed history. With no comparator, diagnose vagueness or
weakness honestly rather than inventing duplication. Compare this batch's actual
choices without a quota or forced matching. REJECT remains legitimate when a
source-faithful, specific bridge cannot be defended. Only Sutrakar supplies
accepted metadata/formula; offline briefs remain qualified research hypotheses.
"""
SOURCE_PATHS = {
    'narada': '../20261119-sutra-comparison/narada-working.json',
    'shandilya': '../20261119-sutra-comparison/shandilya-working.json',
    'candidate_manifest': 'candidate-manifest.json', 'evidence_corpus': 'evidence-corpus.json',
    'corpus_review': 'evidence-corpus-independent-review.json',
    'primary_verification': 'evidence-primary-verification.json',
    'devotional_supplement': 'evidence-devotional-supplement.json',
    'devotional_review': 'evidence-devotional-independent-review.json',
}


def code_bindings():
    """Seal all execution Python and every required reused regression's exact bytes."""
    paths = sorted({p for d in ('src', 'scripts') for p in (ROOT / d).rglob('*.py')}
                   | {ROOT / p for p in REQUIRED_TESTS})
    return {p.relative_to(ROOT).as_posix(): byte_hash(p) for p in paths}


def offline_quality_metadata():
    """Describe the external receipt requirement; never grant test approval."""
    return {'required_tests': list(REQUIRED_TESTS), 'code_sha256': code_bindings(),
            'policy': deepcopy(POLICY), 'paid_calls': 0, 'semantic_quality_certified': False}


def require_offline_gate(path):
    """Check the external exact-code regression receipt before any adapter exists.

    Input: receipt JSON path. Return: unchanged passing receipt. Raise ValueError
    for stale code, missing/duplicate suites or nonzero failures; debug the named
    suite and regenerate the receipt after real offline tests, never edit hashes.
    """
    receipt = load(path)
    rows = receipt.get('tests')
    if (receipt.get('status') != 'PASS' or type(receipt.get('paid_calls')) is not int
            or receipt['paid_calls'] != 0 or receipt.get('code_sha256') != code_bindings()
            or not isinstance(rows, list)):
        raise ValueError('Exact selection code/test receipt required')
    for name in REQUIRED_TESTS:
        found = [r for r in rows if isinstance(r, dict) and r.get('path') == name]
        if (len(found) != 1 or type(found[0].get('passed')) is not int or found[0]['passed'] < 1
                or type(found[0].get('failed')) is not int or found[0]['failed'] != 0
                or type(found[0].get('errors')) is not int or found[0]['errors'] != 0):
            raise ValueError('Required offline regression has not passed: ' + name)
    return receipt


SUPPLEMENT_MENU = 'source-selection-supplement-menu.json'
SUPPLEMENT_CATALOG = 'marathi-bhakti-supplement-verified.json'
SUPPLEMENT_REVIEW = 'source-selection-supplement-menu-review.json'


def _supplement_documents(bundle):
    """Decode three embedded exact-byte proofs; return menu/catalog/review.

    Input: documents keyed by fixed filenames with utf8 and sha256 fields.
    Raise ValueError on missing proofs, hash drift, pending review or unapproved
    IDs. Review binds menu/catalog, never itself through a circular menu hash.
    """
    require = preparation.require
    documents = bundle.get('documents', {})
    require(set(documents) == {SUPPLEMENT_MENU, SUPPLEMENT_CATALOG, SUPPLEMENT_REVIEW},
            'Optional supplement requires exactly three fixed proof files')
    decoded = {}
    for name, proof in documents.items():
        require(isinstance(proof, dict) and isinstance(proof.get('utf8'), str), 'Missing supplement raw proof')
        raw = proof['utf8'].encode('utf-8')
        require(hashlib.sha256(raw).hexdigest() == proof.get('sha256'), 'Optional supplement proof hash drift')
        decoded[name] = json.loads(raw.decode('utf-8-sig'))
    menu, catalog, review = (decoded[n] for n in (SUPPLEMENT_MENU, SUPPLEMENT_CATALOG, SUPPLEMENT_REVIEW))
    require(set(menu) == {'source_catalog_file', 'source_catalog_sha256', 'records'},
            'Optional menu has unknown/circular binding fields')
    catalog_hash = documents[SUPPLEMENT_CATALOG]['sha256']
    require(menu.get('source_catalog_file') == SUPPLEMENT_CATALOG
            and menu.get('source_catalog_sha256') == catalog_hash, 'Optional catalog binding drift')
    verdicts = [review[k] for k in ('status', 'verdict', 'gate') if k in review]
    hashes = [review[k] for k in ('catalog_sha256', 'source_catalog_sha256') if k in review]
    require(verdicts and all(v == 'PASS' for v in verdicts)
            and hashes and all(h == catalog_hash for h in hashes)
            and review.get('menu_sha256') == documents[SUPPLEMENT_MENU]['sha256']
            and not review.get('blockers', []), 'Optional independent PASS/current hashes required')
    records = preparation.indexed(menu.get('records'), 'id', 'optional menu')
    approved = review.get('approved_ids')
    require(isinstance(approved, list) and all(isinstance(i, str) for i in approved)
            and len(approved) == len(set(approved)) and set(approved) == set(records),
            'Optional approved IDs must exactly cover the unique menu')
    decisions = preparation.indexed(review.get('records'), 'id', 'optional per-record review')
    mappings = preparation.indexed(review.get('approved_mappings'), 'id', 'optional approved mappings')
    require(set(decisions) == set(mappings) == set(records) and review.get('issues', []) == [],
            'Optional independent record/mapping coverage or issues drift')
    for ident, row in records.items():
        decision, mapping = decisions[ident], mappings[ident]
        require(decision.get('gate') == 'PASS' and decision.get('issues', []) == []
                and decision.get('pair_id') == mapping.get('pair_id') == row.get('pair_id'),
                'Optional per-record PASS/approved mapping required')
    preparation.indexed(catalog.get('records'), 'id', 'optional catalog')
    return menu, catalog, review


def _baseline_source_packet(evidence, pair_references):
    """Rebuild unchanged source-only baseline from frozen research provenance.

    Return the canonical packet; pair_packet rejects quote/reference drift.
    This is structural replay, not a new independent semantic assessment.
    """
    packet = preparation.pair_packet(evidence, pair_references)
    packet['research_interpretation'] = {k: deepcopy(evidence['research'][k]) for k in (
        'candidate_id', 'source_core_mr', 'relation_kind', 'relation_mr',
        'limitations_mr', 'business_extension_mr', 'evidence_ids')}
    packet['selection_provenance'] = deepcopy(evidence)
    return packet


def _append_supplement(baseline, bundle, eligible_pair_ids, registered_ids):
    """Append only approved references mapped to this pair, without changing baseline.

    Inputs: canonical baseline, exact-byte proof bundle, frozen eligible IDs and
    all baseline registered IDs. Return canonical packet, unchanged if unmapped.
    Fail closed on unsafe mappings, changed catalog context, HOLD or reuse. The
    reviewed human locator is preserved verbatim with its structured edition
    locator; code never generates a different edition locator or business claim.
    """
    require = preparation.require
    # Usability comes from the exact per-record PASS review. An immutable menu
    # may retain its pre-review pending label; HOLD labels never become usable.
    menu, catalog, review = _supplement_documents(bundle)
    catalog_records = preparation.indexed(catalog['records'], 'id', 'optional catalog')
    mapped = []
    for row in menu['records']:
        ident, pair = row['id'], row.get('pair_id')
        require(isinstance(pair, str) and pair in eligible_pair_ids, 'Optional mapping is not eligible')
        require(ident not in registered_ids and re.fullmatch(r'[NS]\d+', ident) is None,
                'Optional ID collides with a registered/Narada/Shandilya reference')
        record = catalog_records.get(ident)
        require(isinstance(record, dict) and record.get('status') in ('VERIFIED', 'USABLE')
                and record.get('blockers') == []
                and row.get('status') in ('USABLE', 'OPTIONAL_PENDING_INDEPENDENT_REVIEW')
                and row.get('mandatory') is False and row.get('selected_by_research_screening') is False,
                'Optional record must have reviewed usable status, no blockers and no mandatory support')
        text = record.get('exact_short_passage')
        require(preparation.text(text) and preparation.byte_hash(text.encode('utf-8'))
                == record.get('passage_sha256') == row.get('passage_sha256'), 'Optional passage hash drift')
        ref = row.get('reference', {})
        require(isinstance(ref, dict) and set(ref) == set(preparation.REFERENCE_FIELDS)
                and all(preparation.text(ref[k]) for k in preparation.REFERENCE_FIELDS),
                'Optional reference requires exact eight fields')
        expected = {'id': ident, 'title': record['work'], 'author': record['author'],
                    'locator': ref['locator'], 'original_text': text,
                    'meaning_mr': record['faithful_meaning_mr'], 'url': record['primary_url'], 'tradition': 'Indian'}
        require(ref == expected and re.match(r'^https?://[^/\s]+', ref['url']) is not None,
                'Optional canonical reference drift')
        context = row.get('context_record', {})
        require(context.get('catalog_record_id') == ident
                and context.get('catalog_record_status') == record['status'], 'Optional context owner/status drift')
        for key in ('verification_level', 'edition', 'locator', 'checked_date_local', 'timezone',
                    'transcription_note_mr', 'original_devotional_context_mr', 'limits_mr',
                    'verification_proof', 'rights', 'meaning_review_status', 'publication_approval', 'blockers'):
            require(key in record and context.get(key) == record[key], 'Optional catalog context drift: ' + key)
        limits = row.get('use_constraints', {})
        require(all(type(limits.get(k)) is int and limits[k] == 1 for k in ('max_pair_mappings', 'max_uses_in_book'))
                and limits.get('book_deduplication_key') == ident
                and limits.get('mandatory_support') is False and limits.get('score_change_allowed') is False
                and limits.get('business_meaning_allowed') is False
                and type(limits.get('additional_quoted_words_allowed')) is int and limits['additional_quoted_words_allowed'] == 0
                and limits.get('main_text_quoted_retelling_allowed') is False,
                'Optional max-use/nonpromotion constraints required')
        words = len(text.split())
        require(type(limits.get('quote_whitespace_words')) is int and limits['quote_whitespace_words'] == words
                and type(limits.get('max_quote_whitespace_words')) is int and limits['max_quote_whitespace_words'] == words,
                'Optional exact short quote cap drift')
        if pair == baseline['selection_provenance']['candidate']['id']:
            evidence = baseline['selection_provenance']
            proof = row.get('eligibility_proof', {})
            require(proof.get('candidate_selection_eligible') is True and proof.get('research_status') == 'SUPPORTED'
                    and proof.get('gate_supported_and_reviewed') is True
                    and proof.get('batch') == evidence['batch_id']
                    and proof.get('request_sha256') == evidence['batch_provenance']['request_sha256']
                    and proof.get('selection_sha256') == evidence['batch_provenance']['selection_sha256']
                    and proof.get('source_hashes') == evidence['candidate']['source_hashes'], 'Optional research provenance drift')
            for name in ('narada', 'shandilya'):
                original = evidence['candidate'][name]
                expected_context = {k: original[k] for k in ('id', 'meaning_mr', 'context_mr', 'source_note') if k in original}
                require(context.get('pair_source_contexts', {}).get(name) == expected_context, 'Optional original pair context drift')
            mapped.append(row)
    if not mapped:
        return deepcopy(baseline)
    result = deepcopy(baseline)
    for row in mapped:
        ident = row['id']; record = catalog_records[ident]
        result['references'].append(deepcopy(row['reference']))
        result['source_contexts'][ident] = {
            'id': ident, 'source_id': ident, 'title': record['work'], 'location': row['reference']['locator'],
            'canonical_passage': record['exact_short_passage'], 'meaning_mr': record['faithful_meaning_mr'],
            'context_mr': record['original_devotional_context_mr'], 'source_note': record['transcription_note_mr'],
            'source_record': {**deepcopy(record), 'source_qualifications': {
                'original_limits_mr': deepcopy(record['limits_mr']),
                'mapping_limits_mr': deepcopy(row.get('mapping_limits_mr', [])),
                'comparative_brief_mr': row.get('comparative_brief_mr'),
                'use_constraints': deepcopy(row['use_constraints']),
                'optional_not_required': True, 'independent_menu_review': 'PASS'}}}
    result['optional_supplement_proof'] = {
        'bundle': deepcopy(bundle), 'eligible_pair_ids': list(eligible_pair_ids),
        'registered_baseline_ids': sorted(registered_ids),
        'baseline_source_packet_sha256': preparation.digest(baseline)}
    return result


def rebuild_source_packet(packet):
    """Pure exact replay for source-only packets, including approved optional refs.

    Input: saved ORIGINAL packet, before case capsule additions. Return: full
    canonical packet including research_interpretation/selection_provenance.
    Raise ValueError on any extra/tampered field or proof. Caller MUST first
    verify the independent saved discussion/original-packet hash: embedded
    self-contained proofs are replay data, not a substitute trust root.
    """
    require = preparation.require
    require(isinstance(packet, dict), 'Original source packet must be a dictionary')
    evidence = packet['selection_provenance']
    require(evidence['research']['status'] == 'SUPPORTED'
            and evidence['independent_review']['verdict'] == 'PASS', 'Original research must be independently supported')
    references = packet['references']
    require(isinstance(references, list) and len({r['id'] for r in references}) == len(references), 'Duplicate source references')
    baseline = _baseline_source_packet(evidence, {r['id']: r for r in references})
    proof = packet.get('optional_supplement_proof')
    expected = baseline
    if proof is not None:
        require(proof.get('baseline_source_packet_sha256') == preparation.digest(baseline), 'Optional baseline hash drift')
        eligible, registered = proof.get('eligible_pair_ids'), proof.get('registered_baseline_ids')
        require(isinstance(eligible, list) and all(isinstance(i, str) for i in eligible)
                and len(set(eligible)) == len(eligible) and evidence['candidate']['id'] in eligible,
                'Optional frozen eligibility registry invalid')
        require(isinstance(registered, list) and all(isinstance(i, str) for i in registered)
                and len(set(registered)) == len(registered)
                and {r['id'] for r in baseline['references']}.issubset(registered), 'Optional baseline reference registry invalid')
        expected = _append_supplement(baseline, proof['bundle'], eligible, set(registered))
    require(packet == expected, 'Exact canonical source packet/proof drift')
    return expected


def load_selection_inputs(input_dir):
    """Read frozen research and optional fixed-name supplement snapshots offline.

    Input: task directory. Return plan/screening/input byte proofs and, only when
    a menu exists, its exact menu/catalog/review bundle. Raise on source/hash
    drift, missing proof or pending independent review, before keys/API calls.
    Neither case inventory nor curator cards participate in this loader.
    """
    directory = Path(input_dir).resolve()
    snapshots = {}
    def read(relative):
        """Read one relative frozen JSON and retain its bytes for snapshot checks.

        Return decoded JSON; filesystem/JSON failures propagate with no provider
        involved. Inspect the resolved input path when diagnosing missing inputs.
        """
        path = (directory / relative).resolve()
        raw = path.read_bytes()
        snapshots[str(path)] = raw
        return json.loads(raw.decode('utf-8-sig'))
    plan = read('research-stage-plan.json')
    for key, relative in SOURCE_PATHS.items():
        if key in plan['source_hashes']:
            read(relative)
            if hashlib.sha256(snapshots[str((directory / relative).resolve())]).hexdigest() != plan['source_hashes'][key]:
                raise ValueError('Frozen source hash drift: ' + key)
    screening = {}
    for index in range(1, len(plan['batches']) + 1):
        name = f'research-{index:03d}'
        paths = {k: f'research-screening/{name}-{k}.json' for k in ('request', 'selection', 'gate')}
        if not all((directory / p).is_file() for p in paths.values()):
            continue
        bundle = {k: read(p) for k, p in paths.items()}
        bundle['files'] = {k: {'path': p, 'sha256': hashlib.sha256(snapshots[str((directory / p).resolve())]).hexdigest()}
                           for k, p in paths.items()}
        screening[name] = bundle
    optional = None
    if (directory / SUPPLEMENT_MENU).is_file():
        for name in (SUPPLEMENT_MENU, SUPPLEMENT_CATALOG, SUPPLEMENT_REVIEW):
            read(name)
        optional = {'documents': {name: {'utf8': snapshots[str((directory / name).resolve())].decode('utf-8'),
                    'sha256': hashlib.sha256(snapshots[str((directory / name).resolve())]).hexdigest()}
                    for name in (SUPPLEMENT_MENU, SUPPLEMENT_CATALOG, SUPPLEMENT_REVIEW)}}
        _supplement_documents(optional)
    for path, raw in snapshots.items():
        if Path(path).read_bytes() != raw:
            raise ValueError('Input changed during snapshot: ' + path)
    result = {'stage_plan': plan, 'screening': screening,
            'input_provenance': {p: {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
                                 for p, raw in snapshots.items()}}
    if optional is not None:
        result['optional_supplement'] = optional
    return result


def build_selection(stage_plan, screening, pair_references, *, optional_supplement=None, pilot_pair_id=None):
    """Build one source-only entry per independently passed research pair.

    Inputs: frozen stage plan, screened batches and canonical eight-field pair
    references; optional_supplement is an exact-byte independently approved
    bundle, not extra research or a business brief. Return a DRAFT registry in
    source-plan order by default (optional pilot_pair_id is a stable move), no generated action
    or case slots. Raise ValueError for incomplete coverage, source/reference
    drift or empty eligibility; diagnose frozen gates rather than curator cards.
    """
    coverage = preparation.research_coverage(stage_plan, screening)
    if coverage['status'] != 'COMPLETE' or not coverage['eligible']:
        raise ValueError('Complete research coverage and nonempty eligible registry required')
    entries = []
    # Optional stable move precedes run-local numbering; no candidate is removed.
    candidates = stage_plan['candidates']
    if pilot_pair_id is not None:
        if not isinstance(pilot_pair_id, str) or pilot_pair_id not in coverage['eligible']:
            raise ValueError('pilot_pair_id must identify an independently eligible pair')
        candidates = ([c for c in candidates if c['id'] == pilot_pair_id]
                      + [c for c in candidates if c['id'] != pilot_pair_id])
    for candidate in candidates:
        ident = candidate['id']
        if ident not in coverage['eligible']:
            continue
        evidence = coverage['eligible'][ident]
        research = evidence['research']
        packet = _baseline_source_packet(evidence, pair_references)
        number = len(entries) + 1
        brief = {'number': number, 'candidate_id': ident,
                 'id': 'source-selection-' + ident,
                 'source_core_mr': deepcopy(research['source_core_mr']),
                 'qualified_business_hypothesis_mr': research['business_extension_mr'],
                 'limitations_mr': research['limitations_mr']}
        entries.append({'number': number, 'candidate_id': ident, 'brief': brief,
                        'source_packet': packet})
    if optional_supplement is not None:
        registered = {ref['id'] for e in entries for ref in e['source_packet']['references']}
        eligible = list(coverage['eligible'])
        for entry in entries:
            entry['source_packet'] = _append_supplement(entry['source_packet'], optional_supplement, eligible, registered)
            rebuild_source_packet(entry['source_packet'])
    if len(entries) != len(coverage['eligible']):
        raise ValueError('Eligible registry coverage mismatch')
    return {'status': 'DRAFT_SOURCE_ONLY_SELECTION', 'entries': entries,
            'coverage': {k: deepcopy(v) for k, v in coverage.items() if k != 'eligible'},
            'author_approval': 'PENDING', 'publication_approved': False}


def selection_contract(stage, payload):
    """Build a discussion-only instruction with Sutrakar metadata and peer scope.

    Inputs: council stage and canonical request. Return: instruction string.
    Raise ValueError for composition/validator stages; inspect the stage name
    rather than routing those calls through a selection writer.
    """
    if stage not in ('position', 'challenge', 'reply', 'proposal', 'peer_review'):
        raise ValueError('Source-only runner prohibits composition/validator stages')
    instruction = writing_contract(stage, payload)
    if stage == 'proposal':
        instruction += (' Own the constructive synthesis after ALL replies: explicitly identify the strongest bounded peer response and assess it as adopt, refine or reject with a source-specific reason in the EXISTING derivation (ACCEPT) or rejection_reason (REJECT). If the initial hypothesis is generic, consider a faithful refinement or alternative yourself; do not demand that another voice write the business decision. No automatic acceptance, extra response fields or extra rounds. For EVERY ACCEPT also supply nonempty Marathi topic_mr, business_decision_mr, '
                        'business_action_mr, and journey_stage chosen ONLY from ' + str(list(preparation.JOURNEY)) +
                        '. topic_mr must have at least two Marathi words; business_decision_mr and business_action_mr at least five each. Keep topic within30words and each decision/action within60words. These are your semantic judgments from the four voices, not copied offline '
                        'assignments. Compare prior_accepted_decisions and within-batch practical '
                        'decisions/actions, not merely broad concepts. No acceptance quota.')
    if stage == 'peer_review':
        instruction += (' Audit REJECT as strictly as ACCEPT: check the strongest actual peer response was assessed, complementary support was not wrongly required to repeat a definition, and no absence-of-literal-business-language or old-broad-theme-only veto was used. For historical decision duplication require a committed THIS-book comparator with the same material condition/action. A cautious tone is not enough for PASS. Review the accepted topic_mr, business_decision_mr, business_action_mr and '
                        'journey_stage too, together with source faithfulness, qualified analogy, '
                        'formula and practical duplication. Anchor issues to exact current fields. '
                        'Review a REJECT reason substantively; never require a formula for rejection.')
    return instruction


def validate_metadata(answer, sources):
    """Validate accepted metadata shape and canonical supplementary support.

    Inputs: proposal envelope and exact number-keyed source packets. Return None;
    raise ValueError for missing/short/non-Marathi fields, unknown journey or bad
    references. These lexical checks never certify semantic business/source fit;
    inspect the field named in the error, then Sutrakar/peer evidence separately.
    """
    rows = answer.get('proposals') if isinstance(answer, dict) else None
    if not isinstance(rows, list):
        raise ValueError('Source-only proposals list required')
    for proposal in rows:
        if not isinstance(proposal, dict):
            raise ValueError('Malformed proposal')
        if proposal.get('decision') != 'ACCEPT':
            continue  # Council validates REJECT/unknown decisions and exact coverage.
        number = proposal.get('number')
        if type(number) is not int or str(number) not in sources:
            raise ValueError('Unknown proposal number')
        require_proposal_support(proposal, sources[str(number)])
        for key in ('topic_mr', 'business_decision_mr', 'business_action_mr'):
            value = proposal.get(key)
            words = re.findall(r'[\u0900-\u097f]+', value) if isinstance(value, str) else []
            minimum = 2 if key == 'topic_mr' else 5
            if len(words) < minimum or len(set(words)) < (2 if key == 'topic_mr' else 3):
                raise ValueError('Accepted proposal requires substantive Marathi ' + key)
            if len(value.split()) > (30 if key == 'topic_mr' else 60):
                raise ValueError('Accepted metadata exceeds compact field limit: ' + key)
        if proposal.get('journey_stage') not in preparation.JOURNEY:
            raise ValueError('Accepted proposal has invalid journey_stage')


class SelectionCalls(book.WritingCalls):
    """Reuse fixed adapters, RLock, timeout and durable provider; discussion only."""
    def __init__(self, provider, work, *, narada_peer_controls=None):
        """Bind optional future-call controls; old/default slots retain their identity."""
        super().__init__(provider, work)
        self.narada_peer_controls = narada_peer_controls
    def voice(self, voice, payload):
        """Send one source-only stage through the fixed durable provider boundary.

        Inputs: one of four voices and its council request. Return: parsed answer.
        Raise for forbidden stages, missing frozen history, invalid accepted
        metadata or provider stops. Debug the local stage/raw checkpoints; the
        council alone owns its bounded schema correction, never a semantic loop.
        """
        if voice not in VOICES:
            raise ValueError('Fifth role is not a selection writer')
        stage = payload['stage']
        if payload.get('source_peer_policy') is not None:
            return self.future_voice(voice, payload)
        instruction = selection_contract(stage, payload)
        view = writing_view(payload)
        # Rename only the paid label; retain the existing rendered literal values.
        if 'forbidden_originals' in view:
            view['literal_formula_exclusions'] = view.pop('forbidden_originals')
        histories = [b.pop('selection_history') for b in view.get('briefs', []) if 'selection_history' in b]
        if len(histories) != 1:
            raise ValueError('Exactly one hash-bound batch history required')
        view['prior_accepted_decisions'] = [h for h in histories[0] if h['status'] == 'ACCEPTED_FOR_CASE_ASSIGNMENT']
        view['held_selection_decisions'] = [h for h in histories[0] if h['status'] == 'HOLD_PEER_REVIEW']
        view['role_focus'] = ROLE_FOCUS[voice]
        size = len(payload['entry_numbers'])
        tokens = max(POLICY['minimum_tokens'], size * POLICY['tokens_per_entry'])
        suffix = '/schema-correction' if 'repair_feedback' in payload else ''
        slot = f"batch/{payload['batch_id']}/{stage}{suffix}"
        with self.lock:
            adapter = self.provider.adapters[voice]
            previous = getattr(adapter, 'effort', None)
            if PROVIDERS[voice] == 'anthropic':
                adapter.effort = POLICY['discussion_effort']
            try:
                try:
                    system = SELECTION_SYSTEM + '\nROLE FOCUS: ' + ROLE_FOCUS[voice]
                    envelope = {'instruction': instruction, 'input': view}
                    options = None
                    if voice == 'narada' and stage == 'peer_review' and self.narada_peer_controls:
                        tokens, options = self.provider.future_request_parameters(
                            voice, slot, system, envelope, tokens,
                            self.narada_peer_controls['max_output_tokens'],
                            {'thinking_level': self.narada_peer_controls['thinking_level']})
                    answer = call_with_lossless_framing(
                        self.provider, voice, slot, system, envelope, tokens,
                        **({'generation_options': options} if options is not None else {}))
                except (ValueError, SourceFirstStopped):
                    # Ambiguous transport/framing failures are fatal, not schema retries.
                    raise SourceFirstStopped('Selection transport/framing stopped; inspect raw checkpoints') from None
            finally:
                if PROVIDERS[voice] == 'anthropic':
                    adapter.effort = previous
        if stage == 'proposal':
            validate_metadata(answer, payload['sources_by_entry'])
        return answer

    def future_voice(self, voice, payload):
        """Call only an opted-in future batch; preserve native ID opinions/provenance.

        Existing settings/slots/call count are reused. Exact model request bytes
        are saved only for new-policy calls; the council owns bounded validation
        and deterministic materialization. No quote or verdict is repaired here.
        """
        from src.orchestration import source_peer_evidence as peer
        rendered = peer.render(voice, payload)
        stage = payload['stage']; suffix = '/schema-correction' if 'repair_feedback' in payload else ''
        slot = f"batch/{payload['batch_id']}/{stage}{suffix}"
        tokens = max(POLICY['minimum_tokens'], len(payload['entry_numbers']) * POLICY['tokens_per_entry'])
        with self.lock:
            adapter = self.provider.adapters[voice]; previous = getattr(adapter, 'effort', None)
            if PROVIDERS[voice] == 'anthropic': adapter.effort = POLICY['discussion_effort']
            try:
                options = None
                if voice == 'narada' and stage == 'peer_review' and self.narada_peer_controls:
                    tokens, options = self.provider.future_request_parameters(voice, slot,
                        rendered['system'], rendered['payload'], tokens,
                        self.narada_peer_controls['max_output_tokens'],
                        {'thinking_level': self.narada_peer_controls['thinking_level']})
                call = {'voice': voice, 'stage': slot, **rendered, 'max_output_tokens': tokens}
                if options: call['generation_options'] = options
                document = self.work / 'peer-evidence' / (peer.digest([voice, slot]) + '-request.json')
                book.save_checkpoint(document, call)
                native = call_with_lossless_framing(self.provider, voice, slot,
                    rendered['system'], rendered['payload'], tokens,
                    **({'generation_options': options} if options is not None else {}))
            finally:
                if PROVIDERS[voice] == 'anthropic': adapter.effort = previous
        if stage == 'proposal': validate_metadata(native, payload['sources_by_entry'])
        if stage != 'peer_review': return native
        return {**native, peer.NATIVE: {'request_document': {'path': str(document.resolve()),
            'sha256': byte_hash(document)}, 'provider_work': str(self.provider.work_dir.resolve()),
            'slot': peer.digest([voice, slot])}}

    def validator(self, *args, **kwargs):
        """Reject every call: the fifth role belongs to later draft validation.

        Inputs are intentionally unused; never returns. RuntimeError identifies
        incorrect caller wiring without invoking a provider or loading keys.
        """
        raise RuntimeError('No validator or composition callback in source-only selection')


def preflight(*, input_dir, research_plan_sha256, pair_references_path,
              pair_references_sha256, forbidden_path, offline_gate, calibration_dir, pilot_pair_id=None):
    """Replay sources/gates, reference bytes, current tests and calibration offline.

    Inputs: explicit frozen paths and expected plan/reference hashes. Return:
    selection, original formulas, immutable binding, input proofs and a separate
    execution receipt. Fail before keys on drift or missing gates. Debug the
    offending input/gate; receipt changes never rewrite immutable cache identity.
    """
    if byte_hash(Path(input_dir) / 'research-stage-plan.json') != research_plan_sha256:
        raise ValueError('Research plan byte hash changed')
    if byte_hash(pair_references_path) != pair_references_sha256:
        raise ValueError('Canonical pair-reference byte hash changed')
    inputs = load_selection_inputs(input_dir)
    references = load(pair_references_path)
    selection = build_selection(inputs['stage_plan'], inputs['screening'], references,
                                optional_supplement=inputs.get('optional_supplement'), pilot_pair_id=pilot_pair_id)
    forbidden = load(forbidden_path)
    if isinstance(forbidden, dict):
        forbidden = forbidden.get('formulas')
    if not isinstance(forbidden, list) or not forbidden or any(not preparation.text(s) for s in forbidden):
        raise ValueError('Explicit nonempty original-formula ledger required')
    gate = require_offline_gate(offline_gate)
    calibration = require_validator_calibration(Path(calibration_dir))
    binding = {'inputs': preparation.digest(inputs['input_provenance']),
               'research_plan': research_plan_sha256, 'references': pair_references_sha256,
               'selection': preparation.digest(selection), 'forbidden': byte_hash(forbidden_path),
               'queue': preparation.digest({'pilot_pair_id': pilot_pair_id,
                   'ordered_pair_ids': [e['candidate_id'] for e in selection['entries']]}),
               'calibration': preparation.digest(calibration),
               'request_contract': preparation.digest({'system': SELECTION_SYSTEM, 'roles': ROLE_FOCUS,
                   'instructions': {stage: selection_contract(stage, {'scope': 'batch', 'entry_numbers': [1],
                       'speaker': 'sutrakar' if stage == 'proposal' else 'narada'})
                       for stage in ('position', 'challenge', 'reply', 'proposal', 'peer_review')}}),
               'policy': preparation.digest(POLICY),
               'roles': preparation.digest({'models': MODELS, 'providers': PROVIDERS, 'rates': RATES})}
    return selection, forbidden, binding, inputs['input_provenance'], {
        'offline_gate_sha256': byte_hash(offline_gate), 'offline_receipt': deepcopy(gate)}


def _never(*args, **kwargs):
    """Guard unreachable composition/assessment/fifth-review council callbacks.

    Ignore inputs; always raise RuntimeError. A failure means selection wiring
    entered a forbidden long-writing path, not an invitation to retry a model.
    """
    raise RuntimeError('Composition, assessment and independent validation are forbidden here')


def run(*, input_dir, research_plan_sha256, pair_references_path, pair_references_sha256,
        forbidden_path, offline_gate, calibration_dir, work, live=False, resume=False,
        target=None, budget=20., claude_cap=15., max_calls=1000, credentials_dir=None,
        registry=None, pilot_pair_id=None, narada_peer_output_tokens=None, narada_thinking_level=None,
        source_peer_policy=None, committed_references=None):
    """Preflight or execute exhaustive source-only batches with exact resume.

    Inputs: explicit frozen paths/hashes, gates, new work path, fixed caps and
    optional logical target. Return a coverage/disposition report. Default is
    read-only; a registry injection is offline only. ValueError fails preflight;
    SourceFirstStopped preserves local raw/checkpoints on execution failure.
    Target never fragments a batch. Inspect receipts and the named stage, never
    rewrite cached hashes or retry unresolved semantic holds automatically.
    """
    if type(live) is not bool or type(resume) is not bool or (live and registry is not None):
        raise ValueError('Explicit live/resume flags; injected registry is offline only')
    if (any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0 for v in (budget, claude_cap))
            or type(max_calls) is not int or max_calls < 1):
        raise ValueError('Positive fixed caps required')
    if source_peer_policy is not None:
        from src.orchestration.source_peer_evidence import VERSIONS
        if source_peer_policy not in VERSIONS or not isinstance(committed_references, list):
            raise ValueError('Explicit future policy and committed reference list (possibly []) required')
    elif committed_references is not None:
        raise ValueError('Committed reference input requires explicit future peer policy')
    future_controls = None
    if narada_peer_output_tokens is not None or narada_thinking_level is not None:
        if (type(narada_peer_output_tokens) is not int or not 16384 <= narada_peer_output_tokens <= 64000
                or not isinstance(narada_thinking_level, str)
                or narada_thinking_level.upper() not in {'LOW', 'MEDIUM', 'HIGH'}):
            raise ValueError('Explicit future Narada headroom >=16384 and supported thinking level required')
        future_controls = {'max_output_tokens': narada_peer_output_tokens,
                           'thinking_level': narada_thinking_level.upper()}
    selection, forbidden, binding, proofs, execution_receipt = preflight(
        input_dir=input_dir, research_plan_sha256=research_plan_sha256,
        pair_references_path=pair_references_path, pair_references_sha256=pair_references_sha256,
        forbidden_path=forbidden_path, offline_gate=offline_gate, calibration_dir=calibration_dir, pilot_pair_id=pilot_pair_id)
    entries = selection['entries']
    target = len(entries) if target is None else target
    if type(target) is not int or not 1 <= target <= len(entries):
        raise ValueError('Target must be a logical candidate number')
    work = _work_path(Path(work))
    for source in (Path(input_dir) / 'research-screening', pair_references_path, forbidden_path, offline_gate, calibration_dir,
                   *proofs, ROOT / 'scripts', ROOT / 'src', ROOT / 'tests'):
        path = Path(source).resolve()
        if work == path or work in path.parents or path in work.parents:
            raise ValueError('New output directory must be disjoint from frozen inputs/code')
    manifest = {'version': POLICY['version'], 'binding': binding, 'live': live,
                'budget': budget, 'claude_cap': claude_cap, 'max_calls': max_calls}
    if resume:
        if load(work / 'run-manifest.json') != manifest:
            raise ValueError('Resume bindings/caps changed')
    elif work.exists():
        raise ValueError('Fresh new work directory required')
    from src.orchestration import source_peer_evidence as peer
    future_batches = {}
    for planned in book.planned_batches(entries):
        if planned[0]['number'] > target: break
        batch_name = 'selection-' + '-'.join(str(e['number']) for e in planned)
        policy = peer.batch_policy(work, batch_name, [e['number'] for e in planned],
            source_peer_policy, committed_references)
        if policy is not None: future_batches[batch_name] = policy['policy_sha256']
    if not live and registry is None:
        return {'status': 'OFFLINE_PREFLIGHT_PASS', 'eligible_count': len(entries),
                'target': target, 'binding': binding, 'paid_calls': 0,
                'pilot_pair_id': pilot_pair_id, 'first_pair_id': entries[0]['candidate_id'],
                **({'future_peer_batches': future_batches} if future_batches else {})}
    if live and credentials_dir is None:
        raise ValueError('Explicit credentials directory required')
    if not resume:
        work.mkdir(parents=True, exist_ok=False)
        save(work / 'run-manifest.json', manifest)
    with _exclusive(work):
        effective_end = max(b[-1]['number'] for b in book.planned_batches(entries) if b[0]['number'] <= target)
        if resume and (work / 'selection-ledger.json').exists():
            previous = load(work / 'selection-ledger.json')
            if max((r['number'] for r in previous['candidates']), default=0) > effective_end:
                raise ValueError('Resume target would regress durable selection coverage')
        receipt_dir = work / 'execution-receipts'
        receipt_dir.mkdir(exist_ok=True)
        ordinal = max((int(p.stem) for p in receipt_dir.glob('*.json') if p.stem.isdigit()), default=0) + 1
        book.save_checkpoint(receipt_dir / f'{ordinal:06d}.json', {**execution_receipt,
            'invocation': ordinal, 'target': target, 'live': live, 'binding': binding,
            'future_narada_peer_controls': future_controls,
            'note': 'Current exact-code test receipt is execution provenance, not provider cache identity.'})
        options = dict(source_hashes=binding, max_usd=budget, max_calls=max_calls,
                       claude_cap_usd=claude_cap, resume=resume)
        provider = (create_live_provider(work / 'provider', credentials_dir=Path(credentials_dir),
                                        enable_live=True, **options) if live else
                    SourceFirstProvider(work / 'provider', registry, **options))
        calls = SelectionCalls(provider, work, narada_peer_controls=future_controls)
        council = ResearchCouncil(work / 'council.db',
            {v: (lambda payload, voice=v: calls.voice(voice, payload)) for v in VOICES},
            _never, _never, max_revisions=1, source_first_selection=True)
        prior, history, ledger = [], [], []
        report = {'status': 'RUNNING', 'eligible_count': len(entries), 'target': target,
                  'pilot_pair_id': pilot_pair_id,
                  'binding': binding, 'considered': [], 'accepted': [], 'rejected': [],
                  'peer_disputed': [], 'held_peer_review': [], 'sutrakar_accepted': [], 'author_approval': 'PENDING', 'publication_approved': False,
                  'composition_calls': 0, 'validator_calls': 0}
        try:
            for batch in book.planned_batches(entries):
                if batch[0]['number'] > target:
                    break
                name = 'selection-' + '-'.join(str(e['number']) for e in batch)
                batch_policy = peer.batch_policy(work, name, [e['number'] for e in batch],
                    source_peer_policy, committed_references, create=True)
                briefs = [deepcopy(e['brief']) for e in batch]
                # One copy in immutable council inputs, compacted to a top-level paid view.
                briefs[0]['selection_history'] = deepcopy(history)
                book.save_checkpoint(work / (name + '-input.json'), {
                    'briefs': briefs, 'prior_formulas': prior, 'prior_accepted_decisions': history,
                    'source_packets': {str(e['number']): e['source_packet'] for e in batch},
                    **({'source_peer_policy': batch_policy} if batch_policy is not None else {})})
                result = council.run_batch_discussion(name, briefs,
                    {str(e['number']): e['source_packet'] for e in batch}, prior, forbidden,
                    **({'source_peer_policy': batch_policy} if batch_policy is not None else {}))
                validate_metadata(result['proposal'], {str(e['number']): e['source_packet'] for e in batch})
                book.save_checkpoint(work / (name + '-discussion.json'), result)
                for item, proposal in zip(batch, sorted(result['proposal']['proposals'], key=lambda p: p['number'])):
                    number = item['number']
                    peers = {voice: next(r for r in value['reviews'] if r['number'] == number)
                             for voice, value in result['peer_review'].items()}
                    disputed = any(r['verdict'] != 'PASS' for r in peers.values())
                    accepted = proposal['decision'] == 'ACCEPT'
                    constraints = result.get('server_constraints', {}).get(str(number), [])
                    disposition = ('HOLD_SERVER_CONSTRAINT' if constraints else
                        ('HOLD_PEER_REVIEW' if disputed else 'ACCEPTED_FOR_CASE_ASSIGNMENT')) if accepted else 'REJECTED'
                    row = {'number': number, 'candidate_id': item['candidate_id'],
                           'proposal': deepcopy(proposal), 'peer_review': peers,
                           'discussion_file': name + '-discussion.json',
                           'discussion_sha256': byte_hash(work / (name + '-discussion.json')),
                           'selection_entry_hash': result['discussion']['_batch']['entry_hashes'][str(number)],
                           'source_packet_sha256': preparation.digest(item['source_packet']),
                           'status': disposition, 'case_curation_eligible': accepted and not disputed and not constraints,
                           'composition_approved': False, 'author_approval': 'PENDING',
                           **({'server_constraints': deepcopy(constraints)} if constraints else {})}
                    book.save_checkpoint(work / f'candidate-{number:03d}.json', row)
                    ledger.append(row)
                    report['considered'].append(item['candidate_id'])
                    if accepted:
                        report['sutrakar_accepted'].append(item['candidate_id'])
                        if constraints:
                            report.setdefault('held_server_constraint', []).append(item['candidate_id'])
                        else:
                            report['held_peer_review' if disputed else 'accepted'].append(item['candidate_id'])
                    else:
                        report['rejected'].append(item['candidate_id'])
                    if disputed:
                        report['peer_disputed'].append(item['candidate_id'])
                    if proposal['decision'] == 'ACCEPT':
                        prior.append(proposal['proposed_sutra'])
                        history.append({'candidate_id': item['candidate_id'], 'number': number,
                            'business_decision_mr': proposal['business_decision_mr'],
                            'business_action_mr': proposal['business_action_mr'],
                            'status': disposition, 'peer_disputed': disputed})
                save(work / 'selection-ledger.json', {'binding': binding, 'candidates': ledger,
                    'prior_accepted_decisions': history, 'prior_formulas': prior})
                save(work / 'report.json', report)
            report['status'] = 'SELECTION_COMPLETE' if len(ledger) == len(entries) else 'SELECTION_CHECKPOINT'
        except Exception as error:
            report.update(status='STOPPED', error_type=type(error).__name__)
            raise SourceFirstStopped('Source-only selection stopped; inspect local checkpoints') from None
        finally:
            report.update(calls=provider.dispatcher.calls,
                reservation_usd=provider.dispatcher.reserved_usd,
                claude_reservation_usd=provider.spend_guard.reserved_usd,
                actual_invoice_usd=None, reservation_is_not_actual_invoice=True)
            save(work / 'report.json', report)
        return report


def main(argv=None):
    """Parse explicit CLI paths/caps and print a sanitized execution result.

    Input: optional argument list (default process argv). Return: zero on success,
    two for runtime/preflight failure; argparse handles malformed flags. Inspect
    local checkpoints for debugging, never print credential-bearing exceptions.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('input-dir', 'research-plan-sha256', 'pair-references',
                 'pair-references-sha256', 'forbidden', 'offline-gate', 'calibration-dir', 'work'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--target', type=int)
    parser.add_argument('--pilot-pair-id', help='Stable-move this eligible pair to the first singleton; retain every other pair')
    parser.add_argument('--budget', type=float, default=20.)
    parser.add_argument('--claude-cap', type=float, default=15.)
    parser.add_argument('--max-calls', type=int, default=1000)
    parser.add_argument('--credentials-dir')
    parser.add_argument('--narada-peer-output-tokens', type=int)
    parser.add_argument('--narada-thinking-level', choices=['LOW','MEDIUM','HIGH','low','medium','high'])
    parser.add_argument('--future-peer-policy', dest='source_peer_policy', choices=[
        'source-selection-evidence-menu-v1','source-selection-reference-menu-v2'])
    parser.add_argument('--committed-references', help='JSON file containing explicit hash-bound actual committed results/candidates')
    args = vars(parser.parse_args(argv))
    if args['committed_references'] is not None:
        args['committed_references'] = load(args['committed_references'])
    args['pair_references_path'] = args.pop('pair_references')
    args['forbidden_path'] = args.pop('forbidden')
    try:
        result = run(**args)
    except Exception as error:
        print(json.dumps({'status': 'STOPPED', 'error_type': type(error).__name__}))
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
