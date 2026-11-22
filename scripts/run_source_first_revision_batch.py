"""Bounded same-source-batch HOLD bridge; never a scheduler or discussion rerun.

API: run(source_dir=..., numbers=[...], candidate_sha256={"2": SHA, ...},
input_sha256=SHA, discussion_sha256=SHA, offline_gate=BASE_RECEIPT,
batch_gate=BATCH_RECEIPT, work=NEW_SHORT_ROOT, committed_results=[],
live=False, resume=False, budget=4., claude_cap=3., max_calls=4,
credentials_dir=None, registry=None). Select one to five original HOLDs.
committed_results is an optional explicit [{path, sha256}] list; export._eligible
validates each current canonical result before any key access. No discovery.

Base receipt must pass unchanged revision.preflight/code_bindings. Separate batch
receipt: status=PASS, paid_calls=0, code_sha256=code_bindings(), and tests containing
one positive passed/zero failed/errors row for TEST. These execution attestations
are outside immutable cache identity; actual protocol, sources, comparators and
fixed models/caps are inside. Receipts are externally supplied, never generated.

Exactly one medium Sutrakar repair and three fresh source-peer calls cover the
whole group, 240s timeout, max(4096,2500*n) output tokens (maximum12500) except
Narada peer review has a 16384-token floor because Gemini thoughts share this
limit. New Narada peer calls explicitly use MEDIUM thinking; no thinking disable.
Actual per-call limits bind provider requests and response provenance. Only the
paid view projects selected entries' existing round maps; originals and derived
full journals remain intact. No added evidence, quote generation, fifth review,
composition, retry/fallback or gate relaxation. Same five configured adapters.
Per-candidate ACCEPT plus three PASS alone permits later case assignment.
Use a new short root such as logs/sf-brev-20261121; single-entry v1 stays intact.
"""
from copy import deepcopy
import argparse
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import run_source_first_revision as r
from scripts import export_source_first_book as export

TEST = 'tests/test_source_first_revision_batch.py'
POLICY = {**r.POLICY, 'version': 'source-first-proposal-batch-revision-v1',
          'max_entries': 5, 'tokens': {'scaled': 'max(4096,2500*n)', 'narada_peer_floor': 16384},
          'narada_peer_generation_options': {'thinking_level': 'MEDIUM'},
          'paid_round_projection': 'selected-only-v1'}
PROPOSAL_EXTRA = r.PROPOSAL_EXTRA.replace('the ONE entry', 'EVERY selected entry') + '''
Cover every original_peer_issues issue_id once; IDs are namespaced by number.
Existing original_proposals/original_peer_reviews describe OLD wording only.
Compare practical decisions against committed_decisions and within this group;
do not accept a duplicate book lesson merely because its formula differs. A
distinct action/condition may share source vocabulary. Do not force acceptance.
Return no new sources, quotations, cases or chapters.
'''
PEER_EXTRA = r.PEER_EXTRA + '''
Cover every selected entry exactly once. Review the whole group's practical
decisions against each other and committed_decisions. Assess the CURRENT
proposal independently; old issue responses are not evidence of resolution.
current_formula_shapes provides deterministic counts, never grammar approval.
'''


def code_bindings():
    """Seal this new bridge/test only; unchanged base preflight seals production."""
    return {name: r.byte_hash(ROOT / name) for name in
            ('scripts/run_source_first_revision_batch.py', TEST)}


def require_batch_gate(path):
    """Require separate exact batch-test attestation before any credential access."""
    gate = r.load(path)
    rows = gate.get('tests')
    if (gate.get('status') != 'PASS' or type(gate.get('paid_calls')) is not int
            or gate['paid_calls'] != 0 or gate.get('code_sha256') != code_bindings()
            or not isinstance(rows, list)):
        raise ValueError('Exact current batch code/test receipt required')
    rows = [v for v in rows if isinstance(v, dict) and v.get('path') == TEST]
    if (len(rows) != 1 or type(rows[0].get('passed')) is not int or rows[0]['passed'] < 1
            or any(type(rows[0].get(k)) is not int or rows[0][k] != 0 for k in ('failed', 'errors'))):
        raise ValueError('Batch regression has not passed')
    return {'path': str(Path(path).resolve()), 'sha256': r.byte_hash(path), 'gate': gate}


def _committed(references):
    """Read explicit hash-bound current READY results; return practical comparators."""
    if not isinstance(references, list):
        raise ValueError('Explicit committed result bindings list required')
    decisions, bindings, seen = [], [], set()
    for ref in references:
        if not isinstance(ref, dict) or set(ref) != {'path', 'sha256'}:
            raise ValueError('Exact committed result path/sha256 required')
        result, _, binding = r._read_bound(ref['path'], ref['sha256'])
        draft, proposal, draft_hash = export._eligible(result)
        if any(not isinstance(proposal.get(k), str) or not proposal[k].strip()
               for k in ('business_decision_mr', 'business_action_mr')):
            raise ValueError('Committed proposal requires its actual practical decision/action')
        if draft['id'] in seen or binding['path'] in {b['path'] for b in bindings}:
            raise ValueError('Duplicate committed result')
        seen.add(draft['id']); bindings.append(binding)
        decisions.append({'id': draft['id'], 'number': draft['number'],
            'draft_sha256': draft_hash, 'new_sutra': draft['new_sutra'],
            'business_decision_mr': proposal.get('business_decision_mr'),
            'business_action_mr': proposal.get('business_action_mr'),
            'journey_stage': proposal['journey_stage'], 'summary_mr': draft.get('summary_mr')})
    return decisions, bindings


def preflight(*, source_dir, numbers, candidate_sha256, input_sha256,
              discussion_sha256, offline_gate, batch_gate, committed_results=None):
    """Validate one shared original batch, every HOLD and both gates before keys."""
    if (not isinstance(numbers, list) or not 1 <= len(numbers) <= 5
            or any(type(n) is not int or n < 1 for n in numbers)
            or len(set(numbers)) != len(numbers) or numbers != sorted(numbers)
            or not isinstance(candidate_sha256, dict)
            or set(candidate_sha256) != {str(n) for n in numbers}):
        raise ValueError('One to five ordered unique numbers and exact SHA map required')
    contexts, input_raw, base_receipt = [], None, None
    for n in numbers:
        context, raw, receipt = r.preflight(source_dir=source_dir, number=n,
            candidate_sha256=candidate_sha256[str(n)], input_sha256=input_sha256,
            discussion_sha256=discussion_sha256, offline_gate=offline_gate)
        if contexts and (context['input_name'] != contexts[0]['input_name']
                or context['discussion_name'] != contexts[0]['discussion_name']
                or raw != input_raw or context['bundle'] != contexts[0]['bundle']):
            raise ValueError('All HOLDs must come from the SAME original source batch')
        contexts.append(context); input_raw, base_receipt = raw, receipt
    batch_receipt = require_batch_gate(batch_gate)
    decisions, committed = _committed([] if committed_results is None else committed_results)
    issues = [{**deepcopy(issue), 'number': c['number'], 'original_issue_id': issue['issue_id'],
               'issue_id': r.selection.preparation.digest({'number': c['number'], 'issue': issue['issue_id']})}
              for c in contexts for issue in c['issues']]
    if len({i['issue_id'] for i in issues}) != len(issues):
        raise ValueError('Original issue namespace collision')
    binding = {'originals': {str(c['number']): c['binding'] for c in contexts},
        'committed_results': committed, 'policy': r.selection.preparation.digest(POLICY),
        'protocol': r.selection.preparation.digest({'system': r.REVISION_SYSTEM,
            'proposal': PROPOSAL_EXTRA, 'peer': PEER_EXTRA,
            'contracts': {stage: r.selection.selection_contract(stage, {'scope': 'batch',
                'entry_numbers': numbers, 'speaker': 'sutrakar' if stage == 'proposal' else 'narada'})
                for stage in ('proposal', 'peer_review')}})}
    return {'contexts': contexts, 'input_raw': input_raw, 'issues': issues,
        'committed_decisions': decisions, 'binding': binding,
        'execution_receipt': {'base': base_receipt, 'batch': batch_receipt}}


def projected_rounds(discussion, numbers):
    """Copy selected numbered cells only into the paid view, retaining all voices."""
    keys = {str(n) for n in numbers}
    projected = {}
    for stage, field in (('position', 'positions'), ('challenge', 'challenges'), ('reply', 'answers')):
        projected[stage] = {}
        for voice, answer in discussion[stage].items():
            row = deepcopy(answer)
            cells = row[field]
            if stage == 'position':
                row[field] = {k: v for k, v in cells.items() if k in keys}
            else:
                row[field] = {peer: {k: v for k, v in entries.items() if k in keys}
                              for peer, entries in cells.items()}
            projected[stage][voice] = row
    return projected


def call_token_limit(voice, stage, count):
    """Keep Gemini peer thinking headroom; scale other calls for one to five HOLDs."""
    if type(count) is not int or not 1 <= count <= 5:
        raise ValueError('One to five entries required for bounded call tokens')
    scaled = max(4096, 2500 * count)
    return max(16384, scaled) if voice == 'narada' and stage == 'peer_review' else scaled


def call_generation_options(voice, stage):
    """Bind explicit Gemini MEDIUM only to new grouped Narada peer calls."""
    return {'thinking_level': 'MEDIUM'} if voice == 'narada' and stage == 'peer_review' else {}


class BatchCalls(r.RevisionCalls):
    """Reuse the base call boundary/lock with a projected grouped request only."""

    def voice(self, voice, payload):
        """Dispatch one exact grouped stage; no schema retry or extra model role."""
        stage = payload['stage']
        if ((stage == 'proposal' and voice != 'sutrakar')
                or (stage == 'peer_review' and voice not in r.VOICES[:-1])
                or stage not in ('proposal', 'peer_review')):
            raise ValueError('Only one repair and three peer stages permitted')
        view = r.selection.writing_view(payload)
        view['discussion'] = projected_rounds(payload['discussion'], payload['entry_numbers'])
        for brief in view['briefs']:
            brief.pop('selection_history', None)
        view['literal_formula_exclusions'] = view.pop('forbidden_originals')
        history = view.pop('revision_history')
        view['prior_accepted_decisions'] = [h for h in history if h['status'] == 'ACCEPTED_FOR_CASE_ASSIGNMENT']
        view['held_selection_decisions'] = [h for h in history if h['status'] == 'HOLD_PEER_REVIEW']
        view['role_focus'] = r.selection.ROLE_FOCUS[voice]
        instruction = r.selection.selection_contract(stage, payload) + (
            PROPOSAL_EXTRA if stage == 'proposal' else PEER_EXTRA)
        system = r.REVISION_SYSTEM + '\nROLE FOCUS: ' + r.selection.ROLE_FOCUS[voice]
        slot = payload['batch_id'] + '/' + stage
        tokens = call_token_limit(voice, stage, len(payload['entry_numbers']))
        generation_options = call_generation_options(voice, stage)
        envelope = {'instruction': instruction, 'input': view}
        r.selection.book.save_checkpoint(self.work / ('request-' + stage + '-' + voice + '.json'),
            {'voice': voice, 'stage': slot, 'system': system, 'payload': envelope,
             'max_output_tokens': tokens, 'generation_options': generation_options,
             'adapter_effort': 'medium' if r.selection.PROVIDERS[voice] == 'anthropic' else 'UNCHANGED'})
        with self.lock:
            adapter = self.provider.adapters[voice]; previous = getattr(adapter, 'effort', None)
            if r.selection.PROVIDERS[voice] == 'anthropic':
                adapter.effort = 'medium'
            try:
                return r.call_with_lossless_framing(self.provider, voice, slot, system, envelope,
                    tokens, generation_options=generation_options)
            finally:
                if r.selection.PROVIDERS[voice] == 'anthropic':
                    adapter.effort = previous


def run(*, source_dir, numbers, candidate_sha256, input_sha256, discussion_sha256,
        offline_gate, batch_gate, work, committed_results=None, live=False, resume=False,
        budget=4., claude_cap=3., max_calls=4, credentials_dir=None, registry=None):
    """Execute only an explicit group, or read-only preflight; preserve every charge."""
    if (type(live) is not bool or type(resume) is not bool or (live and registry is not None)
            or type(max_calls) is not int or max_calls != 4
            or any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0 for v in (budget, claude_cap))):
        raise ValueError('Explicit opt-ins and positive fixed four-call caps required')
    data = preflight(source_dir=source_dir, numbers=numbers, candidate_sha256=candidate_sha256,
        input_sha256=input_sha256, discussion_sha256=discussion_sha256,
        offline_gate=offline_gate, batch_gate=batch_gate, committed_results=committed_results)
    contexts = data['contexts']; first = contexts[0]; work = r._work_path(Path(work))
    for name in (source_dir, offline_gate, batch_gate, ROOT / 'src', ROOT / 'scripts', ROOT / 'tests',
                 *(b['path'] for b in data['binding']['committed_results'])):
        path = Path(name).resolve()
        if path == work or path in work.parents or work in path.parents:
            raise ValueError('New batch root must be disjoint from inputs/code/gates')
    manifest = {'version': POLICY['version'], 'binding': data['binding'], 'live': live,
                'budget': budget, 'claude_cap': claude_cap, 'max_calls': 4}
    if resume:
        if r.load(work / 'run-manifest.json') != manifest:
            raise ValueError('Batch resume binding/cap changed')
        if (work / 'terminal-stop.json').exists():
            raise r.SourceFirstStopped('Terminal batch root; no retry')
    elif work.exists():
        raise ValueError('Fresh short batch revision root required')
    if not live and registry is None:
        return {'status': 'OFFLINE_PREFLIGHT_PASS', 'numbers': numbers, 'paid_calls': 0, 'binding': data['binding']}
    if live and credentials_dir is None:
        raise ValueError('Explicit credentials directory required')
    if not resume:
        work.mkdir(parents=True, exist_ok=False); r.save(work / 'run-manifest.json', manifest)
    with r._exclusive(work):
        if r.load(work / 'run-manifest.json') != manifest or (work / 'terminal-stop.json').exists():
            raise r.SourceFirstStopped('Batch changed/terminated before lock acquisition')
        receipts = work / 'execution-receipts'; receipts.mkdir(exist_ok=True)
        ordinal = max((int(p.stem) for p in receipts.glob('*.json') if p.stem.isdigit()), default=0) + 1
        receipt_path = receipts / f'{ordinal:06d}.json'
        r.save(receipt_path, {**data['execution_receipt'], 'binding': data['binding'], 'paid_execution': live})
        source_hashes = {key: r.selection.preparation.digest(value) for key, value in data['binding'].items()}
        options = dict(source_hashes=source_hashes, max_usd=budget, claude_cap_usd=claude_cap,
                       max_calls=4, resume=resume)
        provider = (r.create_live_provider(work / 'provider', credentials_dir=Path(credentials_dir), enable_live=True, **options)
                    if live else r.SourceFirstProvider(work / 'provider', registry, **options))
        calls = BatchCalls(provider, work); before = provider.dispatcher.calls
        report = {'status': 'RUNNING', 'numbers': numbers, 'composition_calls': 0, 'validator_calls': 0}
        try:
            namespace = 'saved-batch-revision-v1/' + '-'.join(map(str, numbers))
            batch = first['bundle']['discussion']['_batch']
            prior = list(batch['prior_formulas'])
            prior.extend(d['new_sutra'] for d in data['committed_decisions'] if d['new_sutra'] not in prior)
            packets = {str(c['number']): c['packet'] for c in contexts}
            base = {'number': 0, 'scope': 'batch', 'batch_id': namespace, 'entry_numbers': numbers,
                'briefs': [deepcopy(c['brief']) for c in contexts], 'sources': packets, 'sources_by_entry': packets,
                'source_first_selection': r.SOURCE_FIRST_SELECTION, 'prior_formulas': prior,
                'forbidden_originals': batch['forbidden_originals'], 'used_case_ids': [],
                'discussion': deepcopy(first['bundle']['discussion']),
                'revision_history': first['supplied']['prior_accepted_decisions'],
                'original_proposals': {str(c['number']): c['proposal'] for c in contexts},
                'original_peer_reviews': {str(c['number']): c['peers'] for c in contexts},
                'original_peer_issues': data['issues'], 'committed_decisions': data['committed_decisions'],
                'current_formula_shapes': {str(c['number']): r.formula_shape(c['proposal']) for c in contexts}}
            records = []

            def stage(voice, kind, payload):
                """Verify actual durable responses and preserve the first receipt lineage."""
                answer = calls.voice(voice, {**payload, 'stage': kind, 'speaker': voice})
                proof = r._provider_proof(provider, voice, namespace + '/' + kind, answer)
                proof['max_output_tokens'] = call_token_limit(voice, kind, len(numbers))
                proof['generation_options'] = call_generation_options(voice, kind)
                path = work / (kind + '-' + voice + '.json')
                if path.exists():
                    previous = r.load(path)
                    if previous['answer'] != answer or {k: v for k, v in previous['provider'].items()
                            if k not in ('first_validation_receipt', 'request_document')} != proof:
                        raise ValueError('Batch stage checkpoint drift')
                    proof = previous['provider']
                else:
                    request = work / ('request-' + kind + '-' + voice + '.json')
                    proof.update(first_validation_receipt={'path': str(receipt_path.relative_to(work)), 'sha256': r.byte_hash(receipt_path)},
                                 request_document={'path': request.name, 'sha256': r.byte_hash(request)})
                    r.save(path, {'answer': answer, 'provider': proof})
                records.append(proof)
                return answer

            answer = stage('sutrakar', 'proposal', base)
            r._check_answer('proposal', 'sutrakar', answer, base)
            r.selection.validate_metadata(answer, packets)
            proposals = r._numbered(answer['proposals'], numbers, 'Revised proposals')
            responses = r._responses(answer, data['issues'])
            fresh = {}
            for voice in r.VOICES[:-1]:
                request = {**base, 'proposal': {'proposals': answer['proposals']}, 'revision_responses': responses,
                           'current_formula_shapes': {str(n): r.formula_shape(proposals[n]) for n in numbers}}
                reply = stage(voice, 'peer_review', request)
                r._check_answer('peer_review', voice, reply, request)
                fresh[voice] = r._numbered(reply['reviews'], numbers, 'Fresh reviews')
            derived = deepcopy(first['bundle'])
            derived['proposal']['proposals'] = [deepcopy(proposals[p['number']]) if p['number'] in proposals else p
                                                 for p in derived['proposal']['proposals']]
            for voice in r.VOICES[:-1]:
                derived['peer_review'][voice]['reviews'] = [deepcopy(fresh[voice][p['number']]) if p['number'] in proposals else p
                                                            for p in derived['peer_review'][voice]['reviews']]
            for key, decision in (('accepted_numbers', 'ACCEPT'), ('rejected_numbers', 'REJECT')):
                if key in derived:
                    derived[key] = [p['number'] for p in derived['proposal']['proposals'] if p['decision'] == decision]
            provenance = {'version': POLICY['version'], 'numbers': numbers,
                'original_bindings': {str(c['number']): c['original_bindings'] for c in contexts},
                'original_proposals': base['original_proposals'], 'original_peer_reviews': base['original_peer_reviews'],
                'original_issues': data['issues'], 'revision_responses': responses, 'provider_calls': records,
                'original_rounds_sha256': r.selection.preparation.digest(first['bundle']['discussion']),
                'revised_proposals_sha256': r.selection.preparation.digest(proposals),
                'fresh_peer_review_sha256': r.selection.preparation.digest(fresh),
                'committed_results': data['binding']['committed_results'],
                'original_feedback_still_targets_original_proposals': True,
                'fresh_feedback_targets_revised_proposals': True, 'author_approval': 'PENDING', 'publication_approved': False}
            r.selection.book.save_checkpoint(work / 'revision-provenance.json', provenance)
            pointer = {'path': 'revision-provenance.json', 'sha256': r.byte_hash(work / 'revision-provenance.json')}
            derived['revision_provenance'] = pointer
            r.selection.book.save_checkpoint(work / first['discussion_name'], derived)
            r._raw_copy(work / first['input_name'], data['input_raw'])
            candidates = []
            for c in contexts:
                n = c['number']; peers = {v: fresh[v][n] for v in r.VOICES[:-1]}
                accepted = proposals[n]['decision'] == 'ACCEPT'
                passed = all(p['verdict'] == 'PASS' and p['issues'] == [] for p in peers.values())
                status = ('ACCEPTED_FOR_CASE_ASSIGNMENT' if passed else 'HOLD_PEER_REVIEW') if accepted else 'REJECTED'
                candidate = {**deepcopy(c['candidate']), 'proposal': proposals[n], 'peer_review': peers,
                    'discussion_sha256': r.byte_hash(work / first['discussion_name']), 'status': status,
                    'case_curation_eligible': accepted and passed, 'composition_approved': False, 'revision_provenance': pointer}
                path = work / f'candidate-{n:03d}.json'; r.selection.book.save_checkpoint(path, candidate)
                candidates.append({'number': n, 'candidate_id': c['candidate_id'], 'status': status,
                                   'path': path.name, 'sha256': r.byte_hash(path)})
            for c in contexts:
                for proof in c['original_bindings'].values():
                    if r.byte_hash(proof['path']) != proof['sha256']:
                        raise ValueError('Original artifact changed during batch revision')
            for proof in data['binding']['committed_results']:
                if r.byte_hash(proof['path']) != proof['sha256']:
                    raise ValueError('Committed result changed during revision')
            result = {'status': 'COMPLETED', 'numbers': numbers, 'candidates': candidates,
                'discussion': {'path': first['discussion_name'], 'sha256': r.byte_hash(work / first['discussion_name'])},
                'input': {'path': first['input_name'], 'sha256': r.byte_hash(work / first['input_name'])},
                'revision_provenance': pointer, 'author_approval': 'PENDING', 'publication_approved': False}
            r.selection.book.save_checkpoint(work / 'result.json', result); report.update(result)
        except BaseException as error:
            report.update(status='STOPPED', error_type=type(error).__name__)
            r.save(work / 'terminal-stop.json', {'status': 'STOPPED', 'binding': data['binding'], 'error_type': type(error).__name__})
            raise r.SourceFirstStopped('Batch revision stopped; retain raw/reservations, no retry') from None
        finally:
            report.update(calls=provider.dispatcher.calls, new_calls=provider.dispatcher.calls - before,
                reservation_usd=provider.dispatcher.reserved_usd, claude_reservation_usd=provider.spend_guard.reserved_usd,
                actual_invoice_usd=None, reservation_is_not_actual_invoice=True)
            r.save(work / 'report.json', report)
        return report


def main(argv=None):
    """Parse explicit bounded group/bindings; never infer HOLDs or auto-run another group."""
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source-dir', 'candidate-sha256', 'input-sha256', 'discussion-sha256', 'offline-gate', 'batch-gate', 'work'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--numbers', nargs='+', type=int, required=True)
    parser.add_argument('--committed-results', default='[]', help='JSON list of explicit path/sha256 bindings')
    parser.add_argument('--live', action='store_true'); parser.add_argument('--resume', action='store_true')
    parser.add_argument('--budget', type=float, default=4.); parser.add_argument('--claude-cap', type=float, default=3.)
    parser.add_argument('--max-calls', type=int, default=4); parser.add_argument('--credentials-dir')
    try:
        args = vars(parser.parse_args(argv))
        args['candidate_sha256'] = json.loads(args['candidate_sha256'])
        args['committed_results'] = json.loads(args['committed_results'])
        result = run(**args)
    except Exception as error:
        print(json.dumps({'status': 'STOPPED', 'error_type': type(error).__name__})); return 2
    print(json.dumps(result, ensure_ascii=False)); return 0


if __name__ == '__main__':
    raise SystemExit(main())
