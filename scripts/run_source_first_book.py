"""Execute an explicitly frozen Jason prepared plan; never generate a book plan.

CLI requires --plan, --plan-sha256, --forbidden, --calibration-dir,
--offline-gate and a NEW --work directory. Without --live it only preflights.
Use --live --target 1 for the singleton pilot, then --live --resume with the
same inputs/caps to continue. Target counts plan positions, including declines.
Full-plan batches (1, then groups of ten) never depend on the temporary target.

The trusted offline receipt has status=PASS, code_sha256=code_bindings(),
tests=[{path, passed: positive integer, failed: 0, errors: 0}], paid_calls=0.
It must cover REQUIRED_TESTS at these exact bytes; this runner does not issue
its own approval. Existing validator calibration is independently checked.
No credentials are loaded until both gates and resume bindings pass.

Python run(..., registry=fake_registry) exercises the SAME orchestration offline;
injected adapters must be offline. This proves wiring, not semantic quality.
Only this run's fresh folder is written. All output awaits author review; no
export/publication. Unassigned plan cases fail preflight, never get invented.
"""
from copy import deepcopy
import argparse
import hashlib
import json
import math
import re
from pathlib import Path
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import prepare_source_first_book as preparation
from scripts.run_research_book import (
    MODELS, PROVIDERS, RATES, complete_entry, merge_formula_repair,
    merge_exposition_repair, narrow_formula_repair, narrow_exposition_repair,
    parse_object, require_validator_calibration, save,
)
from src.orchestration.independent_review import IndependentReviewer, canonical_hash
from src.orchestration.research_acceptance import CASE_FIELDS
from src.orchestration.research_council import ResearchCouncil, VOICES
from src.orchestration.source_first_provider import (
    SourceFirstProvider, SourceFirstStopped, create_live_provider, _exclusive, _work_path,
)
from src.orchestration.source_first_writing import (
    WRITING_SYSTEM, writing_view, writing_contract, require_proposal_support,
    assess_source_first_entry,
)

REQUIRED_TESTS = (
    'tests/test_source_first_book_runner.py', 'tests/test_source_first_book_plan.py',
    'tests/test_source_first_writing.py', 'tests/test_source_first_council.py',
    'tests/test_source_first_provider.py', 'tests/test_research_council.py',
    'tests/test_independent_review_v2.py', 'tests/test_validator_calibration_runner.py',
)
POLICY = {'version': 1, 'batch_size': 10, 'pilot_size': 1,
          'composition_tokens': 18000, 'composition_effort': 'medium',
          'narrow_repair_tokens': 6000,
          'discussion_effort': 'low', 'timeout_seconds': 240,
          'validator_tokens': 3000, 'validator_temperature': .2, 'max_revisions': 1}


def byte_hash(path):
    """Hash exact local bytes; missing files fail before any credentials."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    """Read one explicit UTF-8 JSON input, never discover or generate a plan."""
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def save_checkpoint(path, value):
    """Preserve successful artifact bytes on replay and reject changed contents.

    A resumed repaired council result has only its latest review-history suffix;
    retain the original full history once the remaining fields match exactly.
    """
    path = Path(path)
    if path.exists():
        previous = load(path)
        if previous == value:
            return
        old = {k: v for k, v in previous.items() if k != 'review_history'}
        new = {k: v for k, v in value.items() if k != 'review_history'}
        history = value.get('review_history', [])
        if old == new and history and previous.get('review_history', [])[-len(history):] == history:
            return
        raise ValueError('Saved output differs from durable checkpoint replay')
    save(path, value)


def code_bindings():
    """Return the complete local execution/test code seal for a trusted test receipt.

    Conservatively includes all Python in src and scripts: dependency edits
    invalidate the gate even if they do not alter the reviewer contract.
    Reading code does not execute it or confer test approval.
    """
    paths = sorted({p for directory in ('src', 'scripts')
                    for p in (ROOT / directory).rglob('*.py')}
                   | {ROOT / p for p in REQUIRED_TESTS})
    return {p.relative_to(ROOT).as_posix(): byte_hash(p) for p in paths}


def offline_quality_metadata():
    """Describe fake-only regression coverage and limits, not a passing receipt."""
    return {'required_tests': list(REQUIRED_TESTS), 'policy': deepcopy(POLICY),
            'paid_calls': 0, 'semantic_quality_certified': False,
            'requires_exact_code_receipt': True, 'author_approval': 'PENDING'}


def require_offline_gate(path):
    """Reject stale/incomplete test attestations before creating live adapters."""
    receipt = load(path)
    rows = receipt.get('tests', [])
    if (receipt.get('status') != 'PASS' or receipt.get('paid_calls') != 0
            or receipt.get('code_sha256') != code_bindings()
            or not isinstance(rows, list)):
        raise ValueError('Exact offline code/test gate required')
    for name in REQUIRED_TESTS:
        matches = [r for r in rows if isinstance(r, dict) and r.get('path') == name]
        if (len(matches) != 1 or type(matches[0].get('passed')) is not int
                or matches[0]['passed'] < 1 or matches[0].get('failed') != 0
                or matches[0].get('errors') != 0):
            raise ValueError('Required offline regression has not passed')
    return receipt


def validate_case_reservations(assignments):
    """Replay preparer identity reservations using only embedded, bound proof.

    Reuse case_inventory for canonical labels and identity checks. Relationship
    records can also name unassigned cases: retain those recorded hashes without
    inventing their missing records, and rehash every assigned member available.
    Exact reservation lists and all recorded assigned-case conflicts must agree.
    Nothing in the supplied plan is normalized in place or repaired.
    """
    require = preparation.require
    cases = [a['canonical_case'] for a in assignments]
    for assignment in assignments:
        case, identity = assignment['canonical_case'], assignment['identity_verification']
        require(identity is None or (isinstance(identity, dict)
                and identity.get('case_id') == case['case_id']
                and identity.get('case_pool_record_sha256') == preparation.digest(case)),
                'Assigned identity verification owner/hash drift')
        require(not (case.get('new_book_status', '').startswith('HOLD')
                     or any(str(flag).startswith('HOLD') for flag in case.get('flags', []))
                     or (identity and identity.get('status') == 'HOLD')),
                'Canonical case or identity HOLD forbids assignment')
    overlay = {'fact_verifications': [a['verification'] for a in assignments],
               'identity_verifications': [a['identity_verification'] for a in assignments
                                          if a['identity_verification'] is not None],
               'cross_case_relationships': []}
    _, _, _, keys, _ = preparation.case_inventory({'case_count': len(cases), 'cases': cases}, overlay)
    hashes = {c['case_id']: preparation.digest(c) for c in cases}
    conflicts = set()
    for assignment in assignments:
        ident = assignment['case_id']
        relations = assignment['relationship_provenance']
        require(isinstance(relations, list), 'Recorded relationship provenance must be a list')
        for relation in relations:
            require(isinstance(relation, dict), 'Malformed recorded relationship')
            ids, bindings = relation.get('case_ids'), relation.get('case_record_bindings')
            require(isinstance(ids, list) and all(preparation.text(i) for i in ids)
                    and ident in ids and len(ids) == len(set(ids))
                    and isinstance(bindings, dict), 'Recorded relationship membership drift')
            require(all(isinstance(bindings.get(i), str)
                        and re.fullmatch(r'[0-9a-f]{64}', bindings[i])
                        and (i not in hashes or bindings[i] == hashes[i]) for i in ids),
                    'Recorded cross-case relationship binding drift')
            if preparation.text(relation.get('person')):
                keys[ident].add(preparation.normalized(relation['person']))
            conflicts.update((i, j) for i in ids for j in ids if i != j and i in hashes and j in hashes)
    used = set()
    for assignment in assignments:
        ident = assignment['case_id']
        require(assignment['identity_reservations'] == sorted(keys[ident]),
                'Canonical identity reservations differ from embedded proof')
        require(not keys[ident].intersection(used), 'Shared canonical identity reservation across assigned cases')
        used.update(keys[ident])
    require(not conflicts, 'Recorded conflicting cross-case relationship forbids co-assignment')


def validate_plan(plan):
    """Check the explicit prepared-plan structure and exact embedded evidence.

    Rebuild reference packets with Jason's adapter; verify case fact bindings
    and limits. The caller's frozen plan hash remains the curation authority,
    not a claim that this structural check establishes semantic truth.
    """
    require = preparation.require
    require(plan.get('status') == 'DRAFT' and plan.get('new_sutras') == 0
            and plan.get('author_approval') == 'PENDING'
            and plan.get('publication_approved') is False
            and plan.get('research_coverage', {}).get('status') == 'COMPLETE',
            'Complete explicit prepared DRAFT plan required')
    entries = plan.get('entries')
    require(isinstance(entries, list) and entries, 'Nonempty prepared entries required')
    used, all_assignments, previous_rank = set(), [], -1
    for number, item in enumerate(entries, 1):
        require(item.get('number') == number and item.get('council_ready') is True,
                'Sequential council-ready entries required; resolve UNASSIGNED cases offline')
        packet, brief = item['source_packet'], item['brief']
        require(brief['number'] == number, 'Prepared brief number drift')
        provenance = packet['selection_provenance']
        require(provenance == brief['selection_provenance']
                and provenance['selection_card_sha256'] == preparation.digest(provenance['selection_card']),
                'Selection provenance drift')
        card = provenance['selection_card']
        expected_brief = {'number': number,
            **{key: card[key] for key in ('topic_mr', 'decision_mr', 'action_mr',
               'source_derivation_mr', 'journey_stage', 'ordering_reason_mr')},
            'pair_reference_ids': list(packet['pair_reference_ids']), 'selection_provenance': provenance}
        require(brief == expected_brief, 'Prepared brief differs from exact selection card')
        require(card['journey_stage'] in preparation.JOURNEY, 'Unknown reader journey stage')
        rank = preparation.JOURNEY[card['journey_stage']]
        require(rank >= previous_rank, 'Ordered cards reverse the reader journey')
        previous_rank = rank
        refs = {r['id']: r for r in packet['references']}
        require(len(refs) == len(packet['references']), 'Duplicate references')
        rebuilt = preparation.pair_packet(provenance['representative'], refs)
        for key in rebuilt:
            if key != 'examples':
                require(packet[key] == rebuilt[key], 'Canonical source/context drift')
        assignments = item['case_assignments']
        require(assignments == packet['case_assignments'] and len(assignments) == 2,
                'Canonical case assignment drift')
        require([a['kind'] for a in assignments] == ['positive', 'caution'], 'Case order drift')
        all_assignments.extend(assignments)
        expected = []
        for assignment in assignments:
            case, check = assignment['canonical_case'], assignment['verification']
            ident = case['case_id']
            require(assignment['status'] == 'DRAFT_ASSIGNED' and assignment['case_id'] == ident
                    and check['case_id'] == ident and assignment['kind'] == case['kind']
                    and ident not in used and check['status'] in ('MATCH', 'QUALIFIED')
                    and check.get('existing_marathi_material_fact_contradiction_found') is not True
                    and check['case_pool_record_sha256'] == preparation.digest(case)
                    and check['existing_text_mr_sha256'] == hashlib.sha256(case['text_mr'].encode()).hexdigest()
                    and check['existing_recorded_fact_sha256'] == hashlib.sha256(case['recorded_fact'].encode()).hexdigest(),
                    'Canonical case/fact verification drift or HOLD')
            used.add(ident)
            expected.append({k: case[k] for k in CASE_FIELDS})
        require(packet['examples'] == expected, 'Canonical case narrative drift')
    validate_case_reservations(all_assignments)
    require(plan['council_payload'] == {
        'briefs': [e['brief'] for e in entries],
        'sources_by_entry': {str(e['number']): e['source_packet'] for e in entries}},
        'Prepared council payload drift')


def planned_batches(entries):
    """Partition the full explicit order: singleton pilot, then stable groups of ten."""
    return [entries[:1]] + [entries[i:i + 10] for i in range(1, len(entries), 10)]


def council_brief(item):
    """Add deterministic identity/chapter fields required by complete_entry.

    Map the prepared journey rank to a positive integer export chapter while
    retaining journey_stage; no theme, source or case changes.
    """
    return {**deepcopy(item['brief']), 'id': f"source-first-{item['number']:03d}",
            'chapter': preparation.JOURNEY[item['brief']['journey_stage']] + 1}


class WritingCalls:
    """Serialize the five fixed adapters with one RLock, retaining council barriers."""

    def __init__(self, provider, work):
        """Bind the durable JSON boundary and its SAME dispatcher/spend guard."""
        self.provider, self.work = provider, Path(work)
        self.lock = threading.RLock()
        for adapter in provider.adapters.values():
            adapter.timeout_seconds = POLICY['timeout_seconds']
        provider.adapters['validator'].temperature = POLICY['validator_temperature']

    def voice(self, voice, payload):
        """Call one council stage via SourceFirstProvider; preserve bounded repairs."""
        kind = 'composition' if payload['stage'].startswith('composition') else payload['stage']
        size = len(payload.get('entry_numbers', [])) or 1
        tokens = POLICY['composition_tokens'] if kind == 'composition' else max(4096, size * 900)
        instruction = writing_contract(kind, payload)
        formula = kind == 'composition' and narrow_formula_repair(payload)
        exposition = kind == 'composition' and narrow_exposition_repair(payload)
        if formula or exposition:
            tokens = POLICY['narrow_repair_tokens']
        if formula:
            instruction = ('Repair ONLY new_sutra, grammar_mr, translation_mr. Return '
                           '{patch:{new_sutra,grammar_mr,translation_mr}}. Keep the existing '
                           'principle and source meaning; formula 2-4 words, <=32 characters.')
        elif exposition:
            instruction = ('Return ONLY {additional_paragraph_mr:...}, one substantive 150-200 '
                           'word Marathi paragraph addressing the short exposition. No padding, '
                           'new facts, examples, formulas or rewritten fields.')
        scope = payload.get('batch_id') if payload.get('scope') == 'batch' else payload['number']
        # Council's sole schema correction is distinct from a failed transport retry.
        suffix = '/schema-correction' if 'repair_feedback' in payload else ''
        slot = f"{payload.get('scope', 'entry')}/{scope}/{payload['stage']}{suffix}"
        with self.lock:
            adapter = self.provider.adapters[voice]
            previous = getattr(adapter, 'effort', None)
            if PROVIDERS[voice] == 'anthropic':
                adapter.effort = 'medium' if kind == 'composition' else 'low'
            try:
                answer = self.provider(voice, slot, WRITING_SYSTEM,
                                       {'instruction': instruction, 'input': writing_view(payload)}, tokens)
            finally:
                if PROVIDERS[voice] == 'anthropic':
                    adapter.effort = previous
        if kind == 'composition':
            if formula:
                answer = merge_formula_repair(answer, payload)
            elif exposition:
                answer = merge_exposition_repair(answer, payload)
            answer = complete_entry(answer, payload)
        return answer

    def validator(self, system, prompt):
        """Forward the calibrated raw prompt unchanged; never JSON-wrap it.

        IndependentReviewer owns one-attempt durability. Save raw/truncated text
        locally before parsing; sanitized errors stop execution without retries.
        """
        with self.lock:
            try:
                self.provider._check_roles()
                response = self.provider.spend_guard.call(
                    self.provider.dispatcher, MODELS['validator'][0], prompt, system,
                    max_output_tokens=3000, allow_truncated=True)
                raw = self.work / 'review-raw'
                raw.mkdir(exist_ok=True)
                name = canonical_hash({'system': system, 'prompt': prompt}) + '.txt'
                (raw / name).write_text(response.content, encoding='utf-8')
                if (response.model_id != MODELS['validator'][1]
                        or response.provider != PROVIDERS['validator'] or response.was_truncated):
                    raise SourceFirstStopped('Independent review identity/truncation stop')
                return parse_object(response.content)
            except Exception:
                raise SourceFirstStopped('Independent review transport/JSON stopped; no retry') from None


def preflight(plan_path, plan_sha256, forbidden_path, calibration_dir, offline_gate):
    """Validate frozen inputs, current code and calibrated reviewer without keys."""
    if byte_hash(plan_path) != plan_sha256:
        raise ValueError('Frozen prepared plan hash changed')
    plan = load(plan_path)
    validate_plan(plan)
    forbidden = load(forbidden_path)
    if isinstance(forbidden, dict):
        forbidden = forbidden['formulas']
    if (not isinstance(forbidden, list) or not forbidden
            or any(not isinstance(v, str) or not v.strip() for v in forbidden)):
        raise ValueError('Explicit nonempty frozen original-formula ledger required')
    gate = require_offline_gate(offline_gate)
    calibration = require_validator_calibration(Path(calibration_dir))
    binding = {'plan': plan_sha256, 'forbidden': byte_hash(forbidden_path),
               'offline_gate': canonical_hash(gate), 'calibration': canonical_hash(calibration),
               'policy': canonical_hash(POLICY),
               'frozen_roles': canonical_hash({'models': MODELS, 'providers': PROVIDERS, 'rates': RATES})}
    return plan, forbidden, binding


def run(*, plan_path, plan_sha256, forbidden_path, calibration_dir, offline_gate,
        work, live=False, resume=False, target=None, budget=20., claude_cap=15.,
        max_calls=1000, credentials_dir=None, registry=None):
    """Run/resume a frozen target using real council and isolated current-draft review.

    No live flag means read-only preflight, except explicit offline fake injection.
    Failed/uncertain quality stops; REJECT is saved without composition. Durable
    council/provider/reviewer caches rebuild prior decisions without re-billing.
    """
    if type(live) is not bool or type(resume) is not bool or (live and registry is not None):
        raise ValueError('Explicit live/resume flags; fake registry is offline only')
    if (any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0 for v in (budget, claude_cap))
            or type(max_calls) is not int or max_calls < 1):
        raise ValueError('Positive fixed spend/call caps required')
    plan, forbidden, binding = preflight(plan_path, plan_sha256, forbidden_path, calibration_dir, offline_gate)
    target = len(plan['entries']) if target is None else target
    if type(target) is not int or not 1 <= target <= len(plan['entries']):
        raise ValueError('Target must be within the explicit plan')
    work = _work_path(Path(work))
    for source in (plan_path, forbidden_path, offline_gate, calibration_dir):
        path = Path(source).resolve()
        if work == path or work in path.parents or path in work.parents:
            raise ValueError('Output must be separate from frozen inputs/calibration')
    manifest = {'version': 1, 'binding': binding, 'live': live, 'budget': budget,
                'claude_cap': claude_cap, 'max_calls': max_calls}
    if resume:
        if load(work / 'run-manifest.json') != manifest:
            raise ValueError('Resume input/code/calibration/cap binding changed')
    elif work.exists():
        raise ValueError('Fresh new work directory required')
    if not live and registry is None:
        return {'status': 'OFFLINE_PREFLIGHT_PASS', 'target': target, 'paid_calls': 0,
                'author_approval': 'PENDING', 'binding': binding}
    if live and credentials_dir is None:
        raise ValueError('Explicit credentials directory required for live execution')
    if not resume:
        work.mkdir(parents=True, exist_ok=False)
        save(work / 'run-manifest.json', manifest)
    # Process-wide lock also excludes concurrent resume of the same run folder.
    with _exclusive(work):
        options = dict(source_hashes=binding, max_usd=budget, max_calls=max_calls,
                       claude_cap_usd=claude_cap, resume=resume)
        if live:
            provider = create_live_provider(work / 'provider', credentials_dir=Path(credentials_dir),
                                            enable_live=True, **options)
        else:
            provider = SourceFirstProvider(work / 'provider', registry, **options)
        calls = WritingCalls(provider, work)
        reviewer = IndependentReviewer(work / 'independent_review_v2.db', calls.validator)
        decisions, prior, used = [], [], set()
        council = ResearchCouncil(work / 'council.db',
            {v: (lambda payload, voice=v: calls.voice(voice, payload)) for v in VOICES},
            lambda _: (_ for _ in ()).throw(RuntimeError('Legacy validator must not run')),
            assess_source_first_entry, max_revisions=1, source_first_selection=True,
            final_review=lambda current: reviewer.review(current['draft'], current['sources'], decisions))
        report = {'status': 'RUNNING', 'target': target, 'completed': [], 'rejected': [],
                  'author_approval': 'PENDING', 'publication_approved': False, 'binding': binding}
        try:
            for batch in planned_batches(plan['entries']):
                if batch[0]['number'] > target:
                    break
                briefs = [council_brief(item) for item in batch]
                name = 'entries-' + '-'.join(str(e['number']) for e in batch)
                discussion = council.run_batch_discussion(name, briefs,
                    {str(e['number']): e['source_packet'] for e in batch}, prior, forbidden)
                save_checkpoint(work / (name + '-discussion.json'), discussion)
                for item, brief in zip(batch, briefs):
                    number = item['number']
                    if number > target:
                        break
                    proposal = next(p for p in discussion['proposal']['proposals'] if p['number'] == number)
                    if proposal['decision'] == 'REJECT':
                        result = {'status': 'REJECTED', 'number': number, 'proposal': proposal,
                                  'author_approval': 'PENDING', 'discussion_file': name + '-discussion.json'}
                        report['rejected'].append(number)
                    else:
                        require_proposal_support(proposal, item['source_packet'])
                        result = council.compose_entry(number, brief, item['source_packet'], prior,
                            forbidden, used, discussion['discussion'], discussion['proposal'], discussion['peer_review'])
                        if result['status'] != 'READY_FOR_AUTHOR_REVIEW':
                            save_checkpoint(work / f'entry-{number:03d}.json', result)
                            report.update(status='QUALITY_STOP', stopped_at=number)
                            break
                        draft = result['draft']
                        prior.append(draft['new_sutra'])
                        used.update(c['case_id'] for c in draft['examples'])
                        decisions.append({'id': draft['id'], 'formula': draft['new_sutra'],
                                          'decision_mr': draft['summary_mr'], 'action_mr': draft['action_mr']})
                        report['completed'].append(number)
                    save_checkpoint(work / f'entry-{number:03d}.json', result)
                    save(work / 'report.json', report)
                if report['status'] == 'QUALITY_STOP':
                    break
            if report['status'] == 'RUNNING':
                report['status'] = 'READY_FOR_AUTHOR_REVIEW'
        except Exception as error:
            report.update(status='STOPPED', error_type=type(error).__name__)
            raise SourceFirstStopped('Source-first book stopped; inspect local checkpoints') from None
        finally:
            report.update(calls=provider.dispatcher.calls, reservation_usd=provider.dispatcher.reserved_usd,
                          claude_reservation_usd=provider.spend_guard.reserved_usd,
                          actual_invoice_usd=None, reservation_is_not_actual_invoice=True)
            save(work / 'report.json', report)
        return report


def main(argv=None):
    """Explicit opt-in CLI; preflight is read-only and exceptions never print keys."""
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('plan', 'plan-sha256', 'forbidden', 'calibration-dir', 'offline-gate', 'work'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--target', type=int)
    parser.add_argument('--budget', type=float, default=20.)
    parser.add_argument('--claude-cap', type=float, default=15.)
    parser.add_argument('--max-calls', type=int, default=1000)
    parser.add_argument('--credentials-dir')
    args = vars(parser.parse_args(argv))
    args['plan_path'] = args.pop('plan')
    args['forbidden_path'] = args.pop('forbidden')
    try:
        report = run(**args)
    except Exception as error:
        print(json.dumps({'status': 'STOPPED', 'error_type': type(error).__name__}))
        return 2
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report['status'] in ('OFFLINE_PREFLIGHT_PASS', 'READY_FOR_AUTHOR_REVIEW') else 2


if __name__ == '__main__':
    raise SystemExit(main())
