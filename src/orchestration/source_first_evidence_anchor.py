"""Exact approved existing-span localization for one exhausted researcher stage.

No SDK, retry, fuzzy matcher or semantic verdict repair. The original provider
result and both FAILED attempts remain immutable. Only explicit offline adoption
inserts a missing council stage, with mandatory receipt authority on every replay.
Execution/code gates are separate operator audit provenance, never paid inputs.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sqlite3

from src.orchestration.source_first_partial_completion import _ro, _require, digest
from src.orchestration.research_council import _json, _check_answer, VOICES, SOURCE_FIRST_SELECTION

KIND = 'EXISTING_EVIDENCE_SPAN_EXTRACTION_V1'
MARKER = 'evidence_span_extraction'
KEY = (0, 'peer_review', 'researcher')
NUMBERS = list(range(72, 82))
SPAN = 'एकं लक्ष्यं विक्षेपेषूदासीनता'
# This known failed production request must never become an ordinary cache hit,
# even if its marker, authority table AND failed history are maliciously removed.
FAILED_CORE = 'b99b3cca39508581ef20ee47c5baf8efec4b2af42b75e1460e48f43cb73f9423'
ERROR = 'ValueError: Invalid review: quote absent from current draft field'


def byte_hash(path):
    """Hash exact existing bytes; filesystem errors propagate without fallback."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_bound(reference):
    """Read only an explicit path/SHA pair; reject drift before interpreting JSON."""
    _require(isinstance(reference, dict) and set(reference) == {'path', 'sha256'}, 'Exact anchor artifact binding required')
    _require(byte_hash(reference['path']) == reference['sha256'], 'Anchor artifact hash drift')
    return json.loads(Path(reference['path']).read_text(encoding='utf-8'))


def reference(path, sha):
    """Return an absolute byte-verified reference; no file is created or changed."""
    ref = {'path': str(Path(path).resolve()), 'sha256': sha}
    read_bound(ref)
    return ref


def _model_request(core, first, config, sources):
    """Rebuild the exact saved second paid request, including first failure feedback.

    Inputs are frozen council data and provider hashes. Returns canonical request
    JSON; imports no keys/adapters and never calls the provider. Drift fails later.
    """
    from scripts import run_source_first_selection as selection
    payload = deepcopy(core)
    if first is not None:
        payload.update(repair_feedback=first['error'], previous_invalid_response=json.loads(first['response_json']),
            instruction='Correct the schema error; return a complete dictionary. Review only literal evidence in the current target.')
    view = selection.writing_view(payload)
    view['literal_formula_exclusions'] = view.pop('forbidden_originals')
    histories = [b.pop('selection_history') for b in view['briefs'] if 'selection_history' in b]
    _require(len(histories) == 1, 'Exact frozen selection history required')
    view['prior_accepted_decisions'] = [h for h in histories[0] if h['status'] == 'ACCEPTED_FOR_CASE_ASSIGNMENT']
    view['held_selection_decisions'] = [h for h in histories[0] if h['status'] == 'HOLD_PEER_REVIEW']
    view['role_focus'] = selection.ROLE_FOCUS['researcher']
    suffix = '/schema-correction' if first is not None else ''
    return {'voice': 'researcher', 'stage': f"batch/{core['batch_id']}/peer_review"+suffix,
        'system': selection.SELECTION_SYSTEM + '\nROLE FOCUS: ' + selection.ROLE_FOCUS['researcher'],
        'payload': {'instruction': selection.selection_contract('peer_review', payload), 'input': view},
        'max_output_tokens': 9000, 'config': config, 'sources': sources}


def prepare_receipt(design_path, design_sha256, approval_path, approval_sha256):
    """Verify the independently approved exact span and rebuild its full10 receipt.

    Reads original data only. Returns a deterministic receipt, never a saved model
    response or cache write. Bad scope, history, request/raw/proposal/approval,
    nonunique span or changed fields fail closed. No generic quote repair exists.
    """
    design_ref = reference(design_path, design_sha256); approval_ref = reference(approval_path, approval_sha256)
    design = read_bound(design_ref); approval = read_bound(approval_ref)
    _require(design.get('schema') == 'source-first-exact-existing-evidence-span-adoption-design-v1', 'Existing-span design only')
    target = design['target']; witness = design['explicit_anchor_witness']; bindings = design['original_bindings']
    _require(target == {'batch': 'selection-'+'-'.join(map(str, NUMBERS)), 'council_db': target.get('council_db'),
        'number': 0, 'stage': 'peer_review', 'speaker': 'researcher', 'latest_attempt': 2,
        'entry_number': 81, 'issue_index': 0, 'json_pointer': '/reviews/9/issues/0/quote'}, 'Only approved latest2 entry81 scope allowed')
    _require(approval.get('status') == 'PASS_SHARED_EXISTING_SPAN_DESIGN_ONLY' and approval.get('gate') == 'PASS_DESIGN_ONLY'
        and approval.get('required_issues') == [] and approval.get('reviewed_saved_design') == design_ref, 'Exact independent span-design GO required')
    dbpath = Path(target['council_db']).resolve(); source = dbpath.parent; provider = source/'provider'
    supplied = read_bound(bindings['input']); manifest = read_bound(bindings['run_manifest'])
    _require(Path(bindings['input']['path']).resolve().parent.samefile(source), 'Original input root mismatch')
    _require(manifest['binding'] == bindings['immutable_business_binding'] and digest(manifest['binding']) == bindings['source_sha256'], 'Frozen business source binding changed')
    with _ro(dbpath) as db:
        db.row_factory = sqlite3.Row
        attempts = [dict(row) for row in db.execute('SELECT * FROM research_attempts WHERE number=? AND stage=? AND speaker=? ORDER BY attempt', KEY)]
        stages = [dict(row) for row in db.execute('SELECT * FROM research_stages WHERE number=0 ORDER BY stage,speaker') if (row['stage'], row['speaker']) != KEY[1:]]
    _require(len(attempts) == 2 and [r['attempt'] for r in attempts] == [1, 2]
        and all(r['state'] == 'FAILED' and r['error'] == ERROR for r in attempts), 'Exactly two original exhausted quote failures required')
    actual_siblings = [{'stage': r['stage'], 'speaker': r['speaker'], 'request_sha256': r['request_hash'],
        'response_json_sha256': hashlib.sha256(r['response_json'].encode()).hexdigest()} for r in stages]
    _require(len(stages) == 15 and sorted(actual_siblings, key=lambda r:(r['stage'],r['speaker'])) ==
        sorted(bindings['all15_cached_stage_bindings'], key=lambda r:(r['stage'],r['speaker'])), 'Original fifteen sibling stages changed')
    saved = {(r['stage'],r['speaker']):json.loads(r['response_json']) for r in stages}
    _require(set(saved) == {(st,v) for st in ('position','challenge','reply') for v in VOICES} |
        {('proposal','sutrakar'),('peer_review','narada'),('peer_review','shandilya')}, 'Exact original sibling coverage required')
    # The frozen input has no exclusions field; the first paid request's complete
    # exclusions are bound through the original first-batch discussion receipt.
    first_path = source/'selection-1-discussion.json'
    first_bundle = json.loads(first_path.read_text(encoding='utf-8'))
    forbidden = first_bundle['discussion']['_batch']['forbidden_originals']
    core = {'number':0,'brief':{'batch_id':target['batch']},'sources':supplied['source_packets'],
        'scope':'batch','batch_id':target['batch'],'briefs':supplied['briefs'],'entry_numbers':NUMBERS,
        'sources_by_entry':supplied['source_packets'],'prior_formulas':supplied['prior_formulas'],
        'forbidden_originals':forbidden,'used_case_ids':[],'source_first_selection':SOURCE_FIRST_SELECTION,
        'discussion':{st:{v:saved[(st,v)] for v in VOICES} for st in ('position','challenge','reply')},
        'proposal':saved[('proposal','sutrakar')],'stage':'peer_review','speaker':'researcher'}
    core_hash = hashlib.sha256(_json(core).encode()).hexdigest()
    _require(core_hash == bindings['core_request_sha256'] and all(r['request_hash'] == core_hash for r in attempts), 'Original core request/proposal drift')
    proposal = core['proposal']; answer = json.loads(attempts[1]['response_json'])
    _require(digest(proposal) == bindings['proposal_parsed_sha256'] and digest(answer) == bindings['latest_response_parsed_sha256'], 'Latest2 response/proposal hash drift')
    expected_attempt = {'attempt':2,'state':'FAILED','error':ERROR,'response_json_sha256':hashlib.sha256(attempts[1]['response_json'].encode()).hexdigest()}
    _require(expected_attempt == bindings['latest_original_failed_attempt'], 'Latest original failed attempt changed')
    with _ro(provider/'boundary.db') as db:
        db.row_factory = sqlite3.Row
        config = db.execute('SELECT digest FROM config').fetchone()[0]
        calls = []
        for suffix in ('','/schema-correction'):
            slot = digest(['researcher', f"batch/{target['batch']}/peer_review"+suffix])
            row = db.execute('SELECT * FROM calls WHERE slot=?',(slot,)).fetchone()
            _require(row is not None, 'Original researcher provider call absent');calls.append(dict(row))
    from src.orchestration.source_first_provider import parse_saved_response
    with _ro(provider/'dispatch.db') as db:
        audits = [{'call_id': k,'record':json.loads(v)} for k,v in db.execute('SELECT call_id,record_json FROM council_dispatch_audit')]
    dispatch = []
    for attempt, call in zip(attempts, calls):
        rawpath = provider/'raw'/(call['slot']+'.txt'); raw = rawpath.read_bytes()
        _require(call['status'] == 'SUCCESS' and byte_hash(rawpath) == call['raw_sha256']
            and parse_saved_response(provider,call['slot'],raw) == json.loads(attempt['response_json']) == json.loads(call['result_json'])
            and digest(json.loads(call['result_json'])) == call['result_sha256'], 'Original actual raw/result/council response mismatch')
        found = [a for a in audits if a['record'].get('response_sha256') == call['raw_sha256']]
        _require(len(found) == 1 and found[0]['record'].get('status') == 'SUCCESS'
            and found[0]['record'].get('role') == 'bharatiya_jnana_specialist'
            and found[0]['record'].get('provider') == 'anthropic'
            and found[0]['record'].get('model_id') == 'claude-sonnet-5-5', 'Actual successful researcher audit required')
        dispatch.append(found[0])
    latest = calls[1]
    _require(calls[0]['source_sha256'] == latest['source_sha256']
        and digest(_model_request(core, None, config, latest['source_sha256'])) == calls[0]['request_sha256'], 'Exact original first paid request mismatch')
    _require(latest['slot'] == bindings['paid_slot'] and latest['request_sha256'] == bindings['actual_paid_request_sha256']
        and latest['source_sha256'] == bindings['source_sha256'] and latest['raw_sha256'] == bindings['raw_latest_response']['sha256']
        and Path(bindings['raw_latest_response']['path']).samefile(provider/'raw'/(latest['slot']+'.txt'))
        and digest(_model_request(core, attempts[0], config, latest['source_sha256'])) == latest['request_sha256'], 'Exact original second paid request mismatch')
    review = answer['reviews'][9]; issue = review['issues'][0]
    proposal81 = next(p for p in proposal['proposals'] if p['number'] == 81); field = proposal81['rejection_reason']; quote = issue['quote']
    _require([r['number'] for r in answer['reviews']] == NUMBERS and review['number'] == 81 and issue['field'] == 'rejection_reason'
        and review['verdict'] == 'REVIEW_REQUIRED' and witness['current_proposal_81_exact'] == proposal81
        and witness['current_field_exact'] == field and witness['invalid_original_issue_exact'] == issue
        and witness['original_quote_exact'] == quote and witness['selected_existing_span_exact'] == SPAN
        and quote.count(SPAN) == field.count(SPAN) == 1 and quote not in field, 'Only exact uniquely witnessed shared span allowed')
    for text,prefix in ((quote,'original_quote'),(field,'current_field')):
        start = witness[prefix+'_start_codepoint'];end = witness[prefix+'_end_codepoint']
        _require(type(start) is int and type(end) is int and text[start:end] == SPAN
            and start == text.index(SPAN) and end == start+len(SPAN), 'Explicit original/field span offset drift')
    _require(witness['new_or_replaced_characters'] == 0 and witness['normalization_performed'] is False
        and witness['morphological_rewrite'] is False
        and witness['original_quote_utf8_sha256'] == hashlib.sha256(quote.encode()).hexdigest()
        and witness['selected_span_utf8_sha256'] == hashlib.sha256(SPAN.encode()).hexdigest()
        and witness['original_quote_selected_utf8_hex'] == witness['current_field_selected_utf8_hex'] == SPAN.encode().hex()
        and witness['current_field_utf8_sha256'] == hashlib.sha256(field.encode()).hexdigest(), 'No generated/normalized quote characters allowed')
    approved = approval['bindings']; exact = approval['exact_selection']
    _require(approved['core_request_sha256'] == core_hash and approved['paid_request_sha256'] == latest['request_sha256']
        and approved['paid_slot'] == latest['slot'] and approved['source_sha256'] == latest['source_sha256']
        and approved['raw_sha256'] == latest['raw_sha256'] and approved['original_review_answer_sha256'] == digest(answer)
        and approved['target_proposal_sha256'] == digest(proposal) and approved['target_full_field_sha256'] == hashlib.sha256(field.encode()).hexdigest()
        and exact['selected_shared_span'] == SPAN and exact['original_full_quote'] == quote
        and exact['original_reason_unchanged'] == issue['reason'] and exact['severity_unchanged'] == issue['severity']
        and exact['verdict_unchanged'] == review['verdict']
        and exact['span_utf8_sha256'] == hashlib.sha256(SPAN.encode()).hexdigest()
        and exact['start_in_original_quote_codepoints'] == witness['original_quote_start_codepoint']
        and exact['end_in_original_quote_codepoints'] == witness['original_quote_end_codepoint']
        and exact['start_in_target_field_codepoints'] == witness['current_field_start_codepoint']
        and exact['end_in_target_field_codepoints'] == witness['current_field_end_codepoint']
        and approval['verification']['all_votes_reasons_severities_fields_otherquotes_identical'] is True, 'Independent witness binding drift')
    patched = deepcopy(answer); patched['reviews'][9]['issues'][0]['quote'] = SPAN
    restored = deepcopy(patched);restored['reviews'][9]['issues'][0]['quote'] = quote
    _require(restored == answer and patched['reviews'][0]['verdict'] == 'PASS'
        and [r['number'] for r in patched['reviews'] if r['verdict']=='REVIEW_REQUIRED'] == [74,75,77,78,79,81], 'All original latest votes/reasons must remain intact')
    _check_answer('peer_review','researcher',patched,core)
    _require(digest(patched) == approved['derived_copy_sha256'] == design['preview_only_validation']['proposed_locally_anchored_answer_sha256'], 'Independently approved full10 copy mismatch')
    return {'kind':KIND,'design':design_ref,'approval':approval_ref,'source_dir':str(source),'council_db':str(dbpath),
        'core_request_sha256':core_hash,'original_attempts':attempts,'original_provider_calls':calls,
        'original_dispatch':dispatch,'original_siblings':actual_siblings,'original_quote':quote,'full_target_field':field,
        'selected_span':SPAN,'anchored_answer':patched,'anchored_answer_sha256':digest(patched),
        'locally_selected_evidence_not_model_requotation':True,'paid_calls':0,'bulk_source_resume_authorized':False}


def verify_receipt(path, expected_sha256):
    """Rebuild every original proof and exact extraction on each receipt/cache replay."""
    ref = reference(path, expected_sha256);receipt = read_bound(ref)
    _require(receipt.get('kind') == KIND, 'Typed existing-span receipt required')
    rebuilt = prepare_receipt(receipt['design']['path'], receipt['design']['sha256'], receipt['approval']['path'], receipt['approval']['sha256'])
    _require(rebuilt == receipt, 'Evidence span receipt/proof drift')
    with _ro(receipt['council_db']) as db:
        stage = db.execute('SELECT request_hash,response_json FROM research_stages WHERE number=? AND stage=? AND speaker=?',KEY).fetchone()
        exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='evidence_span_authorities'").fetchone()
        authority = db.execute('SELECT request_hash,receipt_path,receipt_sha256 FROM evidence_span_authorities WHERE number=? AND stage=? AND speaker=?',KEY).fetchone() if exists else None
    if stage or authority:
        pointer = {'path':str(Path(path).resolve()),'sha256':expected_sha256}
        _require(stage == (receipt['core_request_sha256'],_json({**receipt['anchored_answer'],MARKER:pointer}))
            and authority == (receipt['core_request_sha256'],pointer['path'],expected_sha256), 'Adopted stage/mandatory receipt authority drift')
    return receipt, deepcopy(receipt['anchored_answer'])


def verify_cached_stage(dbpath, db, key, request_hash, saved):
    """Require receipt authority for an adopted cache, including stripped-marker probes.

    Called inside the council transaction before its unchanged validator. Other
    unadopted stages remain unchanged. Missing/conflicting proofs never dispatch.
    """
    exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='evidence_span_authorities'").fetchone()
    authority = db.execute('SELECT request_hash,receipt_path,receipt_sha256 FROM evidence_span_authorities WHERE number=? AND stage=? AND speaker=?',key).fetchone() if exists else None
    failed = db.execute('SELECT state,error FROM research_attempts WHERE number=? AND stage=? AND speaker=? ORDER BY attempt',key).fetchall()
    needs = authority or MARKER in saved or request_hash == FAILED_CORE or (key == KEY and len(failed)==2 and all(r==('FAILED',ERROR) for r in failed))
    if not needs:return
    _require(key == KEY and authority is not None and MARKER in saved, 'Mandatory evidence-span cache authority missing')
    _require(authority[0] == request_hash and saved[MARKER] == {'path':authority[1],'sha256':authority[2]}, 'Evidence-span cache pointer changed')
    receipt,answer = verify_receipt(authority[1],authority[2])
    _require(Path(receipt['council_db']).samefile(dbpath) and receipt['core_request_sha256'] == request_hash
        and saved == {**answer,MARKER:saved[MARKER]}, 'Evidence-span authority belongs to another stage/root/result')


def _adopt_locked(path, sha):
    """Internal operator-only transaction under source lock/current execution gate.

    Reverify receipt inside BEGIN IMMEDIATE; insert the missing stage and its
    authority atomically. Original attempts, raw/provider/audits are never written.
    Conflicts fail; exact applied receipts are idempotent and always reverified.
    """
    receipt,answer = verify_receipt(path,sha);pointer={'path':str(Path(path).resolve()),'sha256':sha}
    saved={**answer,MARKER:pointer};expected=(receipt['core_request_sha256'],_json(saved))
    with sqlite3.connect(receipt['council_db']) as db:
        db.execute('BEGIN IMMEDIATE');verify_receipt(path,sha)
        existing=db.execute('SELECT request_hash,response_json FROM research_stages WHERE number=? AND stage=? AND speaker=?',KEY).fetchone()
        _require(existing is None or existing==expected, 'Conflicting researcher stage already exists')
        db.execute('CREATE TABLE IF NOT EXISTS evidence_span_authorities(number INTEGER,stage TEXT,speaker TEXT,request_hash TEXT NOT NULL,receipt_path TEXT NOT NULL,receipt_sha256 TEXT NOT NULL,PRIMARY KEY(number,stage,speaker))')
        old=db.execute('SELECT request_hash,receipt_path,receipt_sha256 FROM evidence_span_authorities WHERE number=? AND stage=? AND speaker=?',KEY).fetchone()
        authority=(receipt['core_request_sha256'],pointer['path'],sha)
        _require((existing is None and old is None) or (existing==expected and old==authority), 'Conflicting or incomplete evidence-span authority')
        db.execute('INSERT OR IGNORE INTO evidence_span_authorities VALUES (?,?,?,?,?,?)',(*KEY,*authority))
        db.execute('INSERT OR IGNORE INTO research_stages VALUES (?,?,?,?,?)',(*KEY,*expected))
        verify_cached_stage(receipt['council_db'],db,KEY,expected[0],saved)
    return {'status':'EVIDENCE_SPAN_ADOPTED','receipt':pointer,'entry_numbers':NUMBERS,'paid_calls':0,'bulk_source_resume_authorized':False}
