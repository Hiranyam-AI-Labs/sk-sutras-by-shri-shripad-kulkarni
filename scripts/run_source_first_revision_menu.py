"""Opt-in four-call evidence-ID revision of explicitly selected original HOLDs.

No legacy/shared module is modified or monkeypatched. API run(...) retains the
grouped runner arguments and adds menu_gate plus evidence_menu=True. All three
external gates must be current: legacy offline_gate, legacy batch_gate, and the
new two-file menu_gate. Receipts are execution provenance, never cache inputs.
committed_results must bind the six actual READY results, not HOLD history.

review_policy defaults to strict-v1. Explicit unreported-blocking-blind-v2 is
fresh-root only, excludes closed87/88, and binds a new namespace/protocol. Only
an absent severity key on nonempty REVIEW_REQUIRED acquires server unknownness
metadata; every such issue remains blocking. V2 peers receive current evidence
only, while Sutrakar/server retain all original rounds and issues. Optional
all-blocked early-stop is deliberately not implemented; complete three-peer
coverage is retained, at most four calls and never an invented not-run verdict.

Each NEW short root permits one medium Sutrakar proposal and three fresh peers.
Existing full round maps/input bytes are retained; paid views project the group.
Native peer replies contain owner-field IDs only. Server materialization records
exact field selections separately from unchanged raw opinions and provider data.
Failures permanently stop this root; no schema retry, fifth call or composition.
Only ACCEPT + three PASS + no literal constraint becomes case eligible. A
literal constraint preserves all model opinions as HOLD_SERVER_CONSTRAINT;
other rows still materialize. Consumers must retain the candidate status gate.
"""
from copy import deepcopy
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts import run_source_first_revision_batch as batch
from src.orchestration import source_peer_evidence as source_menu
from src.orchestration.source_first_partial_completion import _ro, _require
from src.orchestration.source_first_provider import parse_saved_response
from src.orchestration.research_acceptance import _normalize_formula
from src.orchestration.research_acceptance import _devanagari_word
from src.orchestration import source_first_proposal_recovery as recovery

r = batch.r
TEST = 'tests/test_source_first_revision_menu.py'
ALLOWED_NUMBERS = frozenset((23, 26, 27, 30, 39, 43, 58, 87, 88))
COMMITTED_NUMBERS = (1, 22, 3, 11, 13, 80)
POLICY = {**batch.POLICY, 'version': 'saved-hold-evidence-menu-v1',
          'native_peer_schema': 'owner-field-id-v1', 'schema_retry': False,
          'history': 'six-explicit-ready-decision-action-cards-only',
          'proposal_references': 'canonical-owner-menu-v1',
          'literal_constraint': 'row-local-no-opinion-rewrite-v1'}
STRICT = 'strict-v1'
BLIND = 'unreported-blocking-blind-v2'
UNREPORTED = 'UNREPORTED_BY_MODEL'
V2_POLICY = {**POLICY, 'version':'saved-hold-evidence-menu-v2',
             'native_peer_schema':'absent-only-rqr-severity-v2',
             'severity_missingness':'server-unreported-blocking-v1',
             'fresh_peer_view':'current-only-allowlist-v1'}
SYSTEM = r.REVISION_SYSTEM + source_menu.SYSTEM_APPEND + '''
This is an explicitly opted-in saved HOLD revision, not a new source discussion.
Only prior_accepted_decisions contains committed historical business decisions.
Selected original issues remain quoted against OLD proposals for reconciliation;
their held-comparator assertions are not committed history or a novelty veto.
Do not merely satisfy old objections: correct valid errors and substantively
contest invalid requirements. No source meaning, model or quality gate changes.
Read the complete current proposal before claiming an analogy label is missing.
An existing qualified-modern-application statement must not be ignored or
repeated in every field. Distinguish a false label premise from any legitimate
source, practical, ethical or evidential concern, and address the latter fully.
Sutrakar owns substantive reconciliation and may contest a false premise with
its actual existing wording and source-specific reason. REJECT remains possible.
Both canonical sources need a substantive positive role in a faithful bridge;
listing a source only to say it does not support the application is insufficient.
If that bridge cannot be justified, reject rather than inventing a connection.
'''
PROPOSAL = batch.PROPOSAL_EXTRA.replace('committed_decisions', 'prior_accepted_decisions')
PEER = '''Return ONLY {reviews:[{number,verdict:'PASS'|'REVIEW_REQUIRED',issues:
[{evidence_id,reason,severity}]}]} covering every selected number exactly once.
PASS requires an empty issues list. For each issue select ONLY an ID owned by
that number from proposal_evidence_menu. Do not generate field or quote strings.
The server selects exact CURRENT field text; original issue quotes concern OLD
wording only. Independently assess current source faithfulness, Sanskrit grammar,
qualified modern analogy, both canonical references, genuine supplementary
support and substantive business metadata. Selected supplements may be a subset.
Assess all old issue responses substantively, not as evidence of resolution.
No all-offered-ref, identical-virtue-list or every-field-disclaimer requirement.
Mechanical counts are facts, never grammar certification. Sandhi or an omitted
copula alone is not a defect; examine actual grammar. Shared broad concepts or
held ideas are not novelty vetoes. Only supplied actual committed condition/action
cards and the current group are practical-decision comparators. Review REJECT
reasons equally rigorously; never force acceptance. No extra response keys.
Read existing analogy labels across the whole current proposal; do not demand
a label already present or repeat it in every field. Any substantive source,
evidence, practical or ethical concern must still be evaluated independently.
An evidence ID selects the WHOLE field: read its complete wording and relevant
other fields, acknowledge existing qualifications, then state the actual remaining
defect. Do not claim absent wording or a mechanical count failure contradicted
by current_formula_shapes. Those counts are NOT grammar PASS. An existing analogy
label is NOT proof of a faithful bridge or reliable practical evidence. Sutrakar
must address legitimate application/evidence limits rather than automatically
declaring a reviewer wrong because a label exists. No automatic acceptance.
'''
BLIND_SYSTEM = '''Independently audit the CURRENT proposal using only its actual
canonical sources and qualifications, actual committed decision/action cards
and current mechanical counts. No prior reviewer positions or criticism are
provided; do not infer or reproduce them. Preserve the devotional source object
and scope: God is not profit and spiritual immortality is not corporate survival.
Both Narada and Shandilya need substantive positive grounding for the qualified
modern analogy; supplementary passages may complement rather than repeat a
definition. No literal ancient business instruction is required, but an analogy
label alone proves nothing. Read complete fields and acknowledge actual limits
before identifying the actual remaining source, grammar or practical defect.
Counts are advisory facts, NOT grammar PASS. Reject weak connections without
quota or forced acceptance. Do not edit the proposal, invent sources or write a
chapter. Any REVIEW_REQUIRED remains blocking regardless of severity metadata.
'''
BLIND_PEER = '''Return ONLY {reviews:[{number,verdict:'PASS'|'REVIEW_REQUIRED',
issues:[{evidence_id,reason,severity?}]}]} for every selected number exactly once.
PASS requires issues:[]. REVIEW_REQUIRED requires one or more substantive issues.
Select only that entry's CURRENT owner-field ID; the server selects the WHOLE
exact field text. Do not generate field/quote strings. Read complete current
wording and relevant other fields, including existing analogy labels/limits.
State the actual remaining defect; do not claim missing wording or mechanical
failure contradicted by current_formula_shapes. Current counts are NOT grammar
certification; evaluate actual Sanskrit, source faithfulness and practical limits.
Check both canonical sources and genuine supplementary support. Selected refs
may be a defensible subset. Shared broad concepts are not duplicate decisions;
compare actual condition/action cards and current group only. Review a REJECT
reason equally rigorously; absence of formula for REJECT is required.
If a diagnostic severity is actually reported, supply its nonempty string exactly.
Only on REVIEW_REQUIRED may the severity KEY be omitted: the server records
unknown missingness and still blocks the issue. Do not invent a grade or output
the reserved server marker UNREPORTED_BY_MODEL. Null/blank/wrong types are invalid.
No extra keys, edited proposal, issue clearing or automatic acceptance.
'''


def policy_for(review_policy):
    """Choose an explicit immutable protocol; default strict V1 is never mutated."""
    _require(review_policy in (STRICT,BLIND), 'Unknown review policy')
    return V2_POLICY if review_policy == BLIND else POLICY


def code_bindings():
    """Seal this adapter/test; reused production modules remain under base gates."""
    return {name: r.byte_hash(ROOT / name) for name in
            ('scripts/run_source_first_revision_menu.py', TEST)}


def require_menu_gate(path):
    """Require current external fake-test approval before constructors/credentials."""
    gate = r.load(path); rows = gate.get('tests', [])
    _require(gate.get('status') == 'PASS' and type(gate.get('paid_calls')) is int
        and gate['paid_calls'] == 0 and gate.get('code_sha256') == code_bindings()
        and isinstance(rows, list), 'Current exact menu adapter gate required')
    found = [v for v in rows if isinstance(v, dict) and v.get('path') == TEST]
    _require(len(found) == 1 and type(found[0].get('passed')) is int and found[0]['passed'] > 0
        and all(type(found[0].get(k)) is int and found[0][k] == 0 for k in ('failed', 'errors')),
        'Menu adapter regression must pass')
    return {'path': str(Path(path).resolve()), 'sha256': r.byte_hash(path), 'gate': gate}


def preflight(*, evidence_menu, menu_gate, review_policy=STRICT, **options):
    """Reuse original-HOLD/group proofs, then bind explicit READY-only comparisons.

    Returns validated contexts and immutable protocol inputs; writes nothing.
    Any drift, different batch, non-HOLD, unsupported number or stale gate fails
    before provider/key access. No semantic judgment is created offline.
    """
    _require(evidence_menu is True, 'Explicit evidence_menu=True opt-in required')
    effective = policy_for(review_policy)
    numbers = options['numbers']
    _require(isinstance(numbers, list) and all(type(n) is int and n in ALLOWED_NUMBERS for n in numbers),
        'Only the explicitly authorized remaining HOLD numbers are supported')
    if review_policy == BLIND:
        _require(not set(numbers).intersection((87,88)), 'Closed87/88 calibration cannot be repaid under V2')
    data = batch.preflight(**options)
    receipt = require_menu_gate(menu_gate)
    policy = source_menu.make_policy(options['committed_results'])
    _require(tuple(c['number'] for c in policy['committed_cards']) == COMMITTED_NUMBERS
        and all(p['kind'] == 'ready_result' for p in policy['provenance']),
        'Explicit six actual READY results in canonical book order required')
    data['menu_policy'] = policy
    provenance = verify_original_provenance(data, options['source_dir'])
    data['original_stage_provenance'] = provenance
    protocol = {'system': SYSTEM, 'proposal': PROPOSAL, 'peer': PEER,
        'roles': r.selection.ROLE_FOCUS,
        'proposal_contract': r.selection.selection_contract('proposal', {
            'scope': 'batch', 'entry_numbers': numbers, 'speaker': 'sutrakar'})}
    if review_policy == BLIND:
        protocol.update(peer=BLIND_PEER,peer_system=BLIND_SYSTEM,review_policy=BLIND)
        data['review_policy'] = BLIND
    data['binding'].update(policy=r.selection.preparation.digest(effective),
        committed_menu=policy['policy_sha256'],
        original_stages=r.provider_hash(provenance),
        protocol=r.selection.preparation.digest(protocol))
    data['execution_receipt']['menu'] = receipt
    return data


def verify_original_provenance(data, source_dir):
    """Verify original council checkpoints and mandatory recovered/ID-review proofs.

    Reads only. Derived/forged journals cannot substitute for the actual original
    stage. Current87/88 additionally replay the typed recovery authority and all
    three native-to-field-ID mappings; their old votes are never synthesized.
    """
    context = data['contexts'][0]; bundle = context['bundle']; supplied = context['supplied']
    dbpath = Path(bundle['checkpoint_path']).resolve(); source = Path(source_dir).resolve()
    _require(dbpath.parent.samefile(source), 'Original council checkpoint must belong to source root')
    binding = bundle['discussion']['_batch']; numbers = binding['entry_numbers']; name = binding['batch_id']
    packets = supplied['source_packets']
    base = {'number':0,'brief':{'batch_id':name},'sources':packets,'scope':'batch','batch_id':name,
        'briefs':supplied['briefs'],'entry_numbers':numbers,'sources_by_entry':packets,
        'prior_formulas':supplied['prior_formulas'],'forbidden_originals':binding['forbidden_originals'],
        'used_case_ids':[],'source_first_selection':r.SOURCE_FIRST_SELECTION}
    if 'source_peer_policy' in supplied:
        _require(binding.get('source_peer_policy') == supplied['source_peer_policy'], 'Original frozen policy drift')
        base['source_peer_policy'] = supplied['source_peer_policy']
    proofs = []; discussion = {}
    with _ro(dbpath) as db:
        def checked(stage, voice, request, answer):
            """Match a real saved stage and its exact core request before proof replay."""
            row = db.execute('SELECT request_hash,response_json FROM research_stages WHERE number=0 AND stage=? AND speaker=?',
                (stage,voice)).fetchone()
            expected = hashlib.sha256(r._json(request).encode()).hexdigest()
            _require(row is not None and row[0] == expected and json.loads(row[1]) == answer,
                'Original council stage/request or materialized journal drift')
            proofs.append({'stage':stage,'voice':voice,'request_sha256':row[0],
                'answer_sha256':r.provider_hash(answer)})
            return row
        for stage in ('position','challenge','reply'):
            for voice in r.VOICES:
                checked(stage,voice,{**base,'discussion':discussion,'stage':stage,'speaker':voice},bundle['discussion'][stage][voice])
            discussion[stage] = deepcopy(bundle['discussion'][stage])
        proposal_request = {**base,'discussion':discussion,'stage':'proposal','speaker':'sutrakar'}
        row = checked('proposal','sutrakar',proposal_request,bundle['proposal'])
        recovery.verify_cached_stage(dbpath,db,recovery.KEY,row[0],bundle['proposal'])
        if any(c['number'] in (87,88) for c in data['contexts']):
            _require(recovery.MARKER in bundle['proposal'] and row[0] == recovery.FAILED_CORE,
                'Current87/88 require the real adopted proposal, not a forged original stage')
        for voice in r.VOICES[:-1]:
            request = {**base,'discussion':discussion,'proposal':bundle['proposal'],'stage':'peer_review','speaker':voice}
            row = checked('peer_review',voice,request,bundle['peer_review'][voice])
            if 'source_peer_policy' in base:
                source_menu.verify_cached(dbpath,request,bundle['peer_review'][voice])
            elif 'partial_stage_completion' in bundle['peer_review'][voice]:
                from src.orchestration.source_first_partial_completion import verify_receipt
                pointer = bundle['peer_review'][voice]['partial_stage_completion']; receipt,merged = verify_receipt(pointer['path'],pointer['sha256'])
                _require(receipt['plan']['core_request_sha256'] == row[0]
                    and bundle['peer_review'][voice] == {**merged,'partial_stage_completion':pointer},
                    'Original composite peer authority drift')
    return {'checkpoint_path':str(dbpath),'stages':proofs}


def canonical_reference_menu(request):
    """List only existing owner-packet canonical IDs; never select a source offline."""
    _require(request['sources'] == request['sources_by_entry'], 'Canonical source packet views disagree')
    entries = {}
    for n in request['entry_numbers']:
        packet = request['sources'][str(n)]; pair = packet['source_pair_ids']; refs = packet['references']
        ids = [ref['id'] for ref in refs]
        _require(len(pair) == 2 and len(ids) == len(set(ids)) and set(pair).issubset(ids)
            and all('::' not in i for i in ids) and len(ids)>2, 'Unambiguous canonical reference registry required')
        entries[str(n)] = {'number':n,'required_source_pair_ids':deepcopy(pair),'allowed_reference_ids':ids,
            'supplementary_reference_ids':[i for i in ids if i not in pair],
            'source_packet_sha256':r.provider_hash(packet),'reference_records_sha256':r.provider_hash(refs)}
    body = {'version':POLICY['proposal_references'],'entries':entries}
    return {**body,'menu_sha256':r.provider_hash(body)}


def catalog(request):
    """Return deterministic owner-field IDs bound to this full request/proposal."""
    proposals = r._numbered(request['proposal']['proposals'], request['entry_numbers'], 'Current proposals')
    fields = {}
    for n in request['entry_numbers']:
        for field, value in sorted(proposals[n].items()):
            leaves = [(field, value)] if isinstance(value, str) else [
                (f'{field}.{i}', text) for i, text in enumerate(value) if isinstance(text, str)] if isinstance(value, list) else []
            for field_path, text in leaves:
                fields[f'P{n:03d}.{field_path}'] = {'number': n, 'field': field_path, 'text': text}
    menu = {'request_sha256': r.provider_hash(request),
            'proposal_sha256': r.provider_hash(request['proposal']), 'fields': fields}
    return {**menu, 'menu_sha256': r.provider_hash(menu)}


def materialize(native, request, binding):
    """Copy exact current fields; preserve every native verdict/reason/severity.

    Unknown, foreign, stale IDs, generated quotes, coverage or schema errors fail
    without a retry. Returns canonical reviews and a separate selection proof.
    """
    mode = request.get('review_policy',STRICT); policy_for(mode)
    menu = catalog(request)
    _require(binding == {k: menu[k] for k in ('request_sha256', 'proposal_sha256', 'menu_sha256')},
        'Stale revision evidence menu binding')
    _require(isinstance(native, dict) and set(native) == {'reviews'} and isinstance(native['reviews'], list),
        'Reference-only peer response required')
    r._numbered(native['reviews'], request['entry_numbers'], 'Native peer coverage')
    reviews, mappings = [], []
    for row in native['reviews']:
        _require(set(row) == {'number', 'verdict', 'issues'} and isinstance(row['issues'], list),
            'Exact native review keys required')
        issues = []
        for index, issue in enumerate(row['issues']):
            if mode == BLIND:
                _require(isinstance(issue,dict) and set(issue) in
                    ({'evidence_id','reason'},{'evidence_id','reason','severity'}),
                    'V2 issue must select an ID without generated field/quote')
                reported = 'severity' in issue
                if reported:
                    _require(isinstance(issue['severity'],str) and issue['severity'].strip()
                        and issue['severity'].strip() != UNREPORTED, 'Reported severity must be a real nonempty model string')
                    severity = issue['severity']
                else:
                    _require(row['verdict'] == 'REVIEW_REQUIRED' and bool(row['issues']),
                        'Only absent severity on nonempty REVIEW_REQUIRED may be unreported')
                    severity = UNREPORTED
            else:
                _require(isinstance(issue, dict) and set(issue) == {'evidence_id', 'reason', 'severity'},
                    'Issue must select an ID without generated field/quote')
                severity = issue['severity']
            selected = menu['fields'].get(issue['evidence_id']) if isinstance(issue['evidence_id'], str) else None
            _require(selected is not None and selected['number'] == row['number'], 'Unknown/cross-entry evidence ID')
            issues.append({'field': selected['field'], 'quote': selected['text'],
                'reason': issue['reason'], 'severity': severity})
            selection = {'number': row['number'], 'issue_index': index,
                'evidence_id': issue['evidence_id'], 'text_sha256': r.provider_hash(selected['text'])}
            if mode == BLIND:
                selection.update(native_issue_keys=sorted(issue),native_severity_key_present=reported,
                    canonical_severity=severity,severity_origin='MODEL_REPORTED' if reported else 'SERVER_MISSINGNESS',
                    policy_version=V2_POLICY['version'],issue_remains_blocking=True)
            mappings.append(selection)
        reviews.append({'number': row['number'], 'verdict': row['verdict'], 'issues': issues})
    canonical = {'reviews': reviews}
    r._check_answer('peer_review', request['speaker'], canonical, request)
    proof = {'binding': binding, 'selections': mappings,
        'native_sha256': r.provider_hash(native), 'canonical_sha256': r.provider_hash(canonical),
        'model_opinions_unchanged': True, 'quote_text_selected_not_generated': True}
    if mode == BLIND:
        proof.pop('model_opinions_unchanged')
        proof.update(verdict_reason_evidence_ids_unchanged=True,native_model_output_untouched=True,
            severity_missingness_policy=V2_POLICY['severity_missingness'])
    return canonical,proof


def blind_peer_view(voice, request):
    """Allowlist CURRENT peer evidence only; original context remains server/Sutrakar.

    No old briefs/rounds/proposals/issues/response tables or research business
    hypothesis enter this copy. Canonical passages, meanings and source limits
    use the same existing qualified source projection, with no text regeneration.
    """
    source_view = r.selection.writing_view({'scope':'batch','sources':request['sources']})
    source_view = source_menu._reference_view(source_view)
    source_keys = {'references','examples','source_pair_ids','pair_reference_ids',
        'source_contexts','pair_contexts','source_pair','business_limits_mr'}
    packets = {n:{k:deepcopy(v) for k,v in packet.items() if k in source_keys}
        for n,packet in source_view['sources'].items()}
    return {'number':request['number'],'scope':request['scope'],'batch_id':request['batch_id'],
        'entry_numbers':deepcopy(request['entry_numbers']),'stage':'peer_review','speaker':voice,
        'sources':packets,'proposal':deepcopy(request['proposal']),
        'prior_accepted_decisions':deepcopy(request['menu_policy']['committed_cards']),
        'current_formula_shapes':deepcopy(request['current_formula_shapes']),
        'canonical_reference_menu':canonical_reference_menu(request),
        'menu_policy':{'version':V2_POLICY['version'],'sha256':request['menu_policy']['policy_sha256'],
            'review_policy':BLIND},'role_focus':r.selection.ROLE_FOCUS[voice]}


def render(voice, request):
    """Project selected old rounds and six actual cards, omitting historical lists."""
    stage = request['stage']
    _require(request['speaker'] == voice and ((stage == 'proposal' and voice == 'sutrakar')
        or (stage == 'peer_review' and voice in r.VOICES[:-1])), 'Only four revision stages allowed')
    mode = request.get('review_policy',STRICT); effective = policy_for(mode)
    if mode == BLIND and stage == 'peer_review':
        view = blind_peer_view(voice,request)
        menu = catalog(request)
        view['proposal_evidence_menu'] = {'binding_sha256':menu['menu_sha256'],
            'items':[{'id':i,'number':v['number'],'field':v['field']} for i,v in menu['fields'].items()]}
        return {'system':BLIND_SYSTEM+'\nROLE FOCUS: '+r.selection.ROLE_FOCUS[voice],
            'payload':{'instruction':BLIND_PEER,'input':view}}
    view = r.selection.writing_view(request)
    view['discussion'] = batch.projected_rounds(request['discussion'], request['entry_numbers'])
    for field in ('revision_history', 'committed_decisions', 'menu_policy'):
        view.pop(field, None)
    view = source_menu._strip_history(view)
    view = source_menu._reference_view(view)
    view['prior_accepted_decisions'] = deepcopy(request['menu_policy']['committed_cards'])
    view['canonical_reference_menu'] = canonical_reference_menu(request)
    view['menu_policy'] = {'version': effective['version'], 'sha256': request['menu_policy']['policy_sha256']}
    view['role_focus'] = r.selection.ROLE_FOCUS[voice]
    if stage == 'peer_review':
        menu = catalog(request)
        view['proposal_evidence_menu'] = {'binding_sha256': menu['menu_sha256'],
            'items': [{'id': ident, 'number': value['number'], 'field': value['field']}
                      for ident, value in menu['fields'].items()]}
        instruction = PEER
    else:
        instruction = r.selection.selection_contract(stage, request) + PROPOSAL
        instruction += (' For every ACCEPT select ONLY that entry canonical_reference_menu.allowed_reference_ids, '
            'including BOTH required_source_pair_ids and a genuinely supporting supplementary subset. Never use '
            'pair::component provenance IDs. Keep proposed_sutra Sanskrit,2–4words,at most32Unicodecharacters, '
            'without commas or compound-sentence format. No automatic source-ID or formula correction follows. '
            'current_formula_shapes supplies exact original counts only, never grammar approval.')
    return {'system': SYSTEM + '\nROLE FOCUS: ' + r.selection.ROLE_FOCUS[voice],
        'payload': {'instruction': instruction, 'input': view}}


def request_document(voice, request):
    """Build exact SDK-bound settings plus a separate audit-only effort descriptor."""
    return {'voice': voice, 'stage': request['batch_id'] + '/' + request['stage'],
        **render(voice, request),
        'max_output_tokens': batch.call_token_limit(voice, request['stage'], len(request['entry_numbers'])),
        'generation_options': batch.call_generation_options(voice, request['stage']),
        'adapter_effort': 'medium' if r.selection.PROVIDERS[voice] == 'anthropic' else 'UNCHANGED'}


class MenuCalls(batch.BatchCalls):
    """Reuse grouped locks/adapters/limits with a new immutable request namespace."""
    def voice(self, voice, payload):
        """Dispatch at most once; no schema repair or extra SDK retry is introduced."""
        document = request_document(voice, payload)
        with self.lock:
            adapter = self.provider.adapters[voice]; previous = getattr(adapter, 'effort', None)
            if r.selection.PROVIDERS[voice] == 'anthropic': adapter.effort = 'medium'
            try:
                return r.call_with_lossless_framing(self.provider, voice, document['stage'],
                    document['system'], document['payload'], document['max_output_tokens'],
                    generation_options=document['generation_options'])
            finally:
                if r.selection.PROVIDERS[voice] == 'anthropic': adapter.effort = previous


def _immutable(path, data):
    """Atomically create JSON or verify exact existing content; never overwrite drift."""
    if path.exists():
        _require(r.load(path) == data, 'Saved revision output/proof drift: ' + path.name)
    else:
        r.selection.book.save_checkpoint(path, data)


def stage_record(provider, request, document, native):
    """Verify actual native raw/request proof, then materialize canonical evidence.

    No file writes or provider dispatch. Used equally for initial success and
    every cache resume; altered native/raw/request/mapping cannot become PASS.
    """
    voice = request['speaker']; proof = r._provider_proof(provider, voice, document['stage'], native)
    with _ro(provider.db_path) as db:
        row = db.execute('SELECT result_json FROM calls WHERE slot=?', (proof['slot'],)).fetchone()
    raw = (provider.work_dir / 'raw' / (proof['slot'] + '.txt')).read_bytes()
    _require(parse_saved_response(provider.work_dir, proof['slot'], raw) == native == json.loads(row[0]),
        'Native raw/result bytes or framing proof drift')
    actual = {k: v for k, v in document.items() if k not in ('adapter_effort', 'generation_options')}
    if document['generation_options']: actual['generation_options'] = document['generation_options']
    actual.update(config=provider.config_hash, sources=r.provider_hash(provider.source_hashes))
    _require(r.provider_hash(actual) == proof['request_sha256'], 'Actual model request binding drift')
    mapping = None; canonical = deepcopy(native)
    if request['stage'] == 'peer_review':
        menu = catalog(request)
        canonical, mapping = materialize(native, request,
            {k: menu[k] for k in ('request_sha256', 'proposal_sha256', 'menu_sha256')})
    else:
        r._check_answer('proposal', voice, native, request)
        r.selection.validate_metadata(native, request['sources_by_entry'])
        _require(all(all(_devanagari_word(w) for w in p['proposed_sutra'].split())
            for p in native['proposals'] if p['decision']=='ACCEPT'), 'Sanskrit formula must not use Latin/mixed script')
        r._responses(native, request['original_peer_issues'])
    return {'native': native, 'canonical': canonical, 'provider': proof,
        'core_request_sha256': r.provider_hash(request), 'request_document_sha256': r.provider_hash(document),
        'evidence_mapping': mapping}


def row_constraints(answer, prior, forbidden, policy):
    """Hold objective literal copies locally, without altering model opinions."""
    holds = source_menu.literal_constraints(answer, prior, forbidden, policy)
    accepted = [p for p in answer['proposals'] if p['decision'] == 'ACCEPT']
    for proposal in accepted:
        others = [p['number'] for p in accepted if p['number'] != proposal['number']
            and _normalize_formula(p['proposed_sutra']) == _normalize_formula(proposal['proposed_sutra'])]
        if others: holds.setdefault(str(proposal['number']), []).append(
            {'kind': 'EXACT_NORMALIZED_CURRENT_GROUP_COPY', 'other_numbers': others})
    return holds


def _derive(data, work, answer, fresh, records, constraints):
    """Save derived journals with original rounds/inputs and unselected rows intact."""
    first = data['contexts'][0]; numbers = [c['number'] for c in data['contexts']]
    proposals = r._numbered(answer['proposals'], numbers, 'Revised proposals')
    derived = deepcopy(first['bundle'])
    derived['proposal']['proposals'] = [deepcopy(proposals[p['number']]) if p['number'] in proposals else p
        for p in derived['proposal']['proposals']]
    for voice in r.VOICES[:-1]:
        derived['peer_review'][voice]['reviews'] = [deepcopy(fresh[voice][p['number']]) if p['number'] in proposals else p
            for p in derived['peer_review'][voice]['reviews']]
    for key, decision in (('accepted_numbers', 'ACCEPT'), ('rejected_numbers', 'REJECT')):
        if key in derived: derived[key] = [p['number'] for p in derived['proposal']['proposals'] if p['decision'] == decision]
    effective = policy_for(data.get('review_policy',STRICT))
    provenance = {'version': effective['version'], 'numbers': numbers, 'binding': data['binding'],
        'original_stage_provenance':data['original_stage_provenance'],
        'original_stage_envelopes_exact':{'proposal':deepcopy(first['bundle']['proposal']),
            'peer_review':deepcopy(first['bundle']['peer_review'])},
        'original_bindings': {str(c['number']): c['original_bindings'] for c in data['contexts']},
        'original_proposals': {str(c['number']): c['proposal'] for c in data['contexts']},
        'original_peer_reviews': {str(c['number']): c['peers'] for c in data['contexts']},
        'original_issues': data['issues'], 'revision_responses': r._responses(answer, data['issues']),
        'provider_calls': records, 'original_rounds_sha256': r.provider_hash(first['bundle']['discussion']),
        'fresh_peer_review_sha256': r.provider_hash(fresh), 'revised_proposals_sha256': r.provider_hash(proposals),
        'server_constraints': constraints, 'original_feedback_targets_original_only': True,
        'fresh_feedback_targets_revised_only': True, 'author_approval': 'PENDING', 'publication_approved': False}
    _immutable(work / 'revision-provenance.json', provenance)
    pointer = {'path': 'revision-provenance.json', 'sha256': r.byte_hash(work / 'revision-provenance.json')}
    # Old full-stage receipts attest OLD wording only; retain them above, never
    # falsely attach them to updated selected rows in the derived envelope.
    derived['proposal'].pop(recovery.MARKER,None)
    for voice in r.VOICES[:-1]:
        derived['peer_review'][voice].pop(source_menu.MAPPING,None)
        derived['peer_review'][voice].pop('partial_stage_completion',None)
    derived['revision_provenance'] = pointer
    _immutable(work / first['discussion_name'], derived); r._raw_copy(work / first['input_name'], data['input_raw'])
    candidates = []
    for context in data['contexts']:
        n = context['number']; peers = {v: fresh[v][n] for v in r.VOICES[:-1]}
        accepted = proposals[n]['decision'] == 'ACCEPT'; held = constraints.get(str(n), [])
        passed = all(p['verdict'] == 'PASS' and p['issues'] == [] for p in peers.values())
        status = ('HOLD_SERVER_CONSTRAINT' if held else
            ('ACCEPTED_FOR_CASE_ASSIGNMENT' if passed else 'HOLD_PEER_REVIEW')) if accepted else 'REJECTED'
        candidate = {**deepcopy(context['candidate']), 'proposal': proposals[n], 'peer_review': peers,
            'discussion_sha256': r.byte_hash(work / first['discussion_name']), 'status': status,
            'case_curation_eligible': accepted and passed and not bool(held),
            'composition_approved': False, 'revision_provenance': pointer,
            **({'server_constraints': held} if held else {})}
        path = work / f'candidate-{n:03d}.json'; _immutable(path, candidate)
        candidates.append({'number': n, 'candidate_id': context['candidate_id'], 'status': status,
            'path': path.name, 'sha256': r.byte_hash(path)})
    for context in data['contexts']:
        for proof in context['original_bindings'].values():
            _require(r.byte_hash(proof['path']) == proof['sha256'], 'Original source drift during revision')
    _require(source_menu.make_policy(data['menu_policy']['committed_references']) == data['menu_policy'],
        'Committed READY proof drift during revision')
    result = {'status': 'COMPLETED', 'numbers': numbers, 'candidates': candidates,
        'discussion': {'path': first['discussion_name'], 'sha256': r.byte_hash(work / first['discussion_name'])},
        'input': {'path': first['input_name'], 'sha256': r.byte_hash(work / first['input_name'])},
        'revision_provenance': pointer, 'author_approval': 'PENDING', 'publication_approved': False}
    _immutable(work / 'result.json', result)
    return result


def run(*, source_dir, numbers, candidate_sha256, input_sha256, discussion_sha256,
        offline_gate, batch_gate, menu_gate, work, committed_results, evidence_menu=False,
        live=False, resume=False, budget=4., claude_cap=3., max_calls=4, credentials_dir=None, registry=None,
        review_policy=STRICT):
    """Preflight or run exactly four bounded stages in a NEW opt-in namespace.

    Inputs retain legacy group/hash/cap arguments plus explicit menu policy and
    current adapter gate. Optional review_policy selects new-root V2 only;
    default strict V1 requests/cache identity stay unchanged. Returns derived
    dispositions or read-only preflight.
    Stale bindings/terminal markers fail before constructors. Any execution
    failure retains paid raw/reservations and permanently stops this root.
    """
    _require(type(live) is bool and type(resume) is bool and not (live and registry is not None)
        and type(max_calls) is int and max_calls == 4
        and all(type(v) in (int, float) and math.isfinite(v) and v > 0 for v in (budget, claude_cap)),
        'Explicit flags and positive four-call fixed caps required')
    effective = policy_for(review_policy)
    data = preflight(evidence_menu=evidence_menu, menu_gate=menu_gate, review_policy=review_policy, source_dir=source_dir,
        numbers=numbers, candidate_sha256=candidate_sha256, input_sha256=input_sha256,
        discussion_sha256=discussion_sha256, offline_gate=offline_gate, batch_gate=batch_gate,
        committed_results=committed_results)
    work = r._work_path(Path(work))
    for value in (source_dir, offline_gate, batch_gate, menu_gate, ROOT / 'src', ROOT / 'scripts', ROOT / 'tests',
                  *(p['path'] for p in data['menu_policy']['committed_references'])):
        path = Path(value).resolve()
        _require(path != work and path not in work.parents and work not in path.parents, 'Output must be disjoint')
    manifest = {'version': effective['version'], 'binding': data['binding'], 'live': live,
        'budget': budget, 'claude_cap': claude_cap, 'max_calls': 4}
    if resume:
        _require(r.load(work / 'run-manifest.json') == manifest, 'Resume immutable binding/cap drift')
        if (work / 'terminal-stop.json').exists(): raise r.SourceFirstStopped('Terminal revision root; no retry')
    else: _require(not work.exists(), 'Fresh revision menu root required')
    if not live and registry is None:
        return {'status': 'OFFLINE_PREFLIGHT_PASS', 'numbers': numbers, 'binding': data['binding'], 'paid_calls': 0}
    _require(not live or credentials_dir is not None, 'Explicit credentials directory required')
    if not resume:
        work.mkdir(parents=True, exist_ok=False); r.save(work / 'run-manifest.json', manifest)
    with r._exclusive(work):
        _require(r.load(work / 'run-manifest.json') == manifest, 'Manifest changed under lock')
        if (work / 'terminal-stop.json').exists(): raise r.SourceFirstStopped('Terminal marker under lock')
        receipts = work / 'execution-receipts'; receipts.mkdir(exist_ok=True)
        ordinal = max((int(p.stem) for p in receipts.glob('*.json') if p.stem.isdigit()), default=0) + 1
        receipt_path = receipts / f'{ordinal:06d}.json'
        r.save(receipt_path, {**data['execution_receipt'], 'binding': data['binding'], 'paid_execution': live})
        options = dict(source_hashes={k: r.provider_hash(v) for k, v in data['binding'].items()},
            max_usd=budget, claude_cap_usd=claude_cap, max_calls=4, resume=resume)
        provider = (r.create_live_provider(work / 'provider', credentials_dir=Path(credentials_dir), enable_live=True, **options)
            if live else r.SourceFirstProvider(work / 'provider', registry, **options))
        calls = MenuCalls(provider, work); before = provider.dispatcher.calls
        report = {'status': 'RUNNING', 'numbers': numbers, 'composition_calls': 0, 'validator_calls': 0}
        try:
            first = data['contexts'][0]; oldbatch = first['bundle']['discussion']['_batch']
            prior = list(oldbatch['prior_formulas'])
            packets = {str(c['number']): c['packet'] for c in data['contexts']}
            base = {'number': 0, 'scope': 'batch', 'batch_id': effective['version'] + '/' + '-'.join(map(str, numbers)),
                'entry_numbers': numbers, 'source_first_selection': r.SOURCE_FIRST_SELECTION,
                'briefs': [deepcopy(c['brief']) for c in data['contexts']], 'sources': packets, 'sources_by_entry': packets,
                'prior_formulas': prior, 'forbidden_originals': oldbatch['forbidden_originals'], 'used_case_ids': [],
                'discussion': deepcopy(first['bundle']['discussion']), 'menu_policy': data['menu_policy'],
                'original_proposals': {str(c['number']): c['proposal'] for c in data['contexts']},
                'original_peer_reviews': {str(c['number']): c['peers'] for c in data['contexts']},
                'original_peer_issues': data['issues'],
                'current_formula_shapes': {str(c['number']): r.formula_shape(c['proposal']) for c in data['contexts']}}
            if review_policy == BLIND:base['review_policy'] = BLIND
            records = []

            def stage(voice, kind, payload):
                """Verify old native mapping before reuse; otherwise dispatch one slot."""
                request = {**payload, 'speaker': voice, 'stage': kind}; document = request_document(voice, request)
                path = work / (kind + '-' + voice + '.json')
                request_path = work / ('request-' + kind + '-' + voice + '.json')
                if path.exists():
                    saved = r.load(path)
                    _require(r.load(request_path) == document, 'Historical actual request document drift')
                    record = stage_record(provider, request, document, saved['native'])
                    _require({k: v for k, v in saved.items() if k != 'first_validation_receipt'} == record,
                        'Mandatory native-to-canonical mapping checkpoint drift')
                    pointer = saved['first_validation_receipt']
                    _require(r.byte_hash(work / pointer['path']) == pointer['sha256'], 'Historical execution receipt drift')
                else:
                    _require(not (work / 'result.json').exists(), 'Completed revision missing mandatory stage proof')
                    _immutable(request_path, document)
                    native = calls.voice(voice, request)
                    record = stage_record(provider, request, document, native)
                    saved = {**record, 'first_validation_receipt': {'path': str(receipt_path.relative_to(work)),
                        'sha256': r.byte_hash(receipt_path)}}
                    _immutable(path, saved)
                records.append({'stage_file': path.name, 'sha256': r.byte_hash(path),
                    'request_file': request_path.name, 'request_sha256': r.byte_hash(request_path),
                    'provider': saved['provider']})
                return deepcopy(saved['canonical'])

            answer = stage('sutrakar', 'proposal', base)
            proposals = r._numbered(answer['proposals'], numbers, 'Revised proposals')
            fresh = {}
            for voice in r.VOICES[:-1]:
                request = {**base, 'proposal': {'proposals': answer['proposals']},
                    'revision_responses': r._responses(answer, data['issues']),
                    'current_formula_shapes': {str(n): r.formula_shape(proposals[n]) for n in numbers}}
                reply = stage(voice, 'peer_review', request)
                fresh[voice] = r._numbered(reply['reviews'], numbers, 'Fresh canonical reviews')
            constraints = row_constraints(answer, prior, oldbatch['forbidden_originals'], data['menu_policy'])
            report.update(_derive(data, work, answer, fresh, records, constraints))
        except BaseException as error:
            report.update(status='STOPPED', error_type=type(error).__name__)
            r.save(work / 'terminal-stop.json', {'status': 'STOPPED', 'binding': data['binding'],
                'error_type': type(error).__name__})
            raise r.SourceFirstStopped('Evidence-menu revision stopped; retain raw/reservations, no retry') from None
        finally:
            report.update(calls=provider.dispatcher.calls, new_calls=provider.dispatcher.calls - before,
                reservation_usd=provider.dispatcher.reserved_usd, claude_reservation_usd=provider.spend_guard.reserved_usd,
                actual_invoice_usd=None, reservation_is_not_actual_invoice=True)
            r.save(work / 'report.json', report)
        return report


def main(argv=None):
    """Parse one explicit new-menu group; default read-only, never schedule another."""
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source-dir', 'candidate-sha256', 'input-sha256', 'discussion-sha256',
                 'offline-gate', 'batch-gate', 'menu-gate', 'work', 'committed-results'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--numbers', nargs='+', type=int, required=True)
    parser.add_argument('--evidence-menu', action='store_true')
    parser.add_argument('--review-policy', choices=(STRICT,BLIND), default=STRICT,
                        help='Explicit fresh-root V2 unknown-severity and opinion-blind peers; default strict V1')
    parser.add_argument('--live', action='store_true'); parser.add_argument('--resume', action='store_true')
    parser.add_argument('--budget', type=float, default=4.); parser.add_argument('--claude-cap', type=float, default=3.)
    parser.add_argument('--max-calls', type=int, default=4); parser.add_argument('--credentials-dir')
    try:
        args = vars(parser.parse_args(argv)); args['candidate_sha256'] = json.loads(args['candidate_sha256'])
        args['committed_results'] = r.load(args['committed_results'])
        result = run(**args)
    except Exception as error:
        print(json.dumps({'status': 'STOPPED', 'error_type': type(error).__name__})); return 2
    print(json.dumps(result, ensure_ascii=False)); return 0


if __name__ == '__main__':
    raise SystemExit(main())
