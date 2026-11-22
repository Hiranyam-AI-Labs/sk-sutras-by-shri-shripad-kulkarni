"""Exact independently approved latest82..91 ID/one-comma cache adoption.

No provider factory, paid retry, guessed source, formula generation or failure
reset. Both original FAILED/null attempts, provider data and twelve paid rounds
remain immutable. Only a separate receipt/operator may insert the missing
canonical proposal stage. Every later cache hit rebuilds mandatory authority.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sqlite3

from src.orchestration.source_first_evidence_anchor import byte_hash, read_bound, reference
from src.orchestration.source_first_partial_completion import _ro, _require, digest
from src.orchestration.research_council import _json, _check_answer, VOICES, SOURCE_FIRST_SELECTION
from src.orchestration.research_acceptance import _devanagari_word

KIND = 'EXACT_PROPOSAL_ID_COMMA_RECONCILIATION_V1'
MARKER = 'exact_proposal_recovery'
TABLE = 'exact_proposal_recovery_authorities'
KEY = (0, 'proposal', 'sutrakar')
NUMBERS = list(range(82, 92))
FAILED_CORE = '7d65b94f11e309ea571c81da4aee58e07ded7e4df0d6af59cdd955a22de3b69d'
NATIVE_HASH = 'fc4813f74893b83389f9b506404d960dbcb2edb2bdc7f5cd0b8a8ea0a18a2a64'
DERIVED_HASH = '8710c8c98fe6ab292d3cb77a0c75f694da692fc716e339b0dd88275bd2d7640a'
ERROR = 'ValueError: Accepted source-first proposal requires both sutras and supplementary support'
BEFORE = 'शीलं प्रथमं, कौशलं पश्चात्'
AFTER = 'शीलं प्रथमं कौशलं पश्चात्'
PATHS = {'/proposals/5/selected_source_ids/2', '/proposals/5/selected_source_ids/3',
         '/proposals/6/selected_source_ids/2', '/proposals/5/proposed_sutra'}


def _text_hash(text):
    """Hash exact UTF8 text, without Unicode, whitespace or punctuation normalization."""
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _changes(left, right, path=''):
    """Return changed JSON leaves; container/coverage changes fail rather than vanish."""
    if isinstance(left, dict) and isinstance(right, dict):
        _require(set(left) == set(right), 'Unexpected proposal key change')
        return [row for k in left for row in _changes(left[k], right[k], path+'/'+k)]
    if isinstance(left, list) and isinstance(right, list):
        _require(len(left) == len(right), 'Unexpected proposal list coverage change')
        return [row for i, (a, b) in enumerate(zip(left, right)) for row in _changes(a, b, path+'/'+str(i))]
    return [] if left == right else [{'json_pointer': path, 'before': left, 'after': right}]


def transform(native, packets, design):
    """Apply exactly three attested owner-ID translations and one comma omission.

    Returns a detached copy. Native decisions/formulas except the single comma,
    all other fields and source passages remain unchanged. This is no grammar or
    semantic certification; unchanged validators and fresh reviewers still apply.
    """
    from scripts import run_source_first_selection as selection
    _require(digest(native) == NATIVE_HASH == design['latest_native_parsed_sha256'], 'Only exact latest native proposal allowed')
    proposals = native.get('proposals')
    _require(isinstance(proposals, list) and [p['number'] for p in proposals] == NUMBERS
        and [p['number'] for p in proposals if p['decision'] == 'ACCEPT'] == [87, 88]
        and next(p for p in proposals if p['number'] == 91)['decision'] == 'REJECT', 'Latest ten decisions/ordering changed')
    result = deepcopy(native); aliases = design['exact_alias_witnesses']
    _require(len(aliases) == 3 and {a['json_pointer'] for a in aliases} == PATHS-{'/proposals/5/proposed_sutra'},
        'Only three approved ID positions allowed')
    seen_alias, seen_target = set(), set()
    for witness in aliases:
        parts = witness['json_pointer'].split('/'); row = result['proposals'][int(parts[2])]
        n = row['number']; index = int(parts[-1]); old = witness['from']; new = witness['to']; packet = packets[str(n)]
        selection.rebuild_source_packet(packet)
        _require(witness['number'] == n and n in (87,88) and digest(packet) == witness['source_packet_sha256']
            and row['selected_source_ids'][index] == old, 'Alias scope/input drift')
        owner = packet['research_interpretation']['candidate_id']
        refs = [r for r in packet['references'] if r['id'] == new]
        contexts = [(k,c) for k,c in packet['source_contexts'].items() if c.get('id') == old]
        evidence = [e for e in packet['selection_provenance']['research']['selected_evidence'] if e['source_id'] == new]
        _require(len(refs) == len(contexts) == len(evidence) == 1, 'Ambiguous or absent registered alias witness')
        ref = refs[0]; key, context = contexts[0]; record = evidence[0]
        _require(set(ref) == set(selection.preparation.REFERENCE_FIELDS)
            and owner == witness['owner_candidate_id'] == context.get('candidate_id')
            and key == new == context.get('source_id') and old in packet['research_interpretation']['evidence_ids']
            and old not in {r['id'] for r in packet['references']} and new not in packet['source_pair_ids']
            and record['eligible'] is True and record['verified'] is True,
            'Cross-owner, canonical-pair override or unverified alias')
        _require(ref['original_text'] == context['canonical_passage'] == record['canonical_passage']
            and ref['meaning_mr'] == context['meaning_mr'] == record['meaning_mr']
            and context['context_mr'] == record['context_mr']
            and ref['locator'] == context['location'] == record['location']
            and context['source_sha256'] == record['source_sha256']
            and _text_hash(ref['original_text']) == record['passage_sha256'] == context['passage_sha256']
            == witness['passage_sha256'] and digest(ref) == witness['canonical_reference_sha256']
            and digest(context) == witness['source_context_sha256']
            and digest(record) == witness['research_evidence_sha256']
            and digest(record['meaning_mr']) == witness['meaning_sha256']
            and digest(record['context_mr']) == witness['context_sha256'], 'Reference passage/meaning/context witness drift')
        _require((n,old) not in seen_alias and (n,new) not in seen_target, 'Alias mapping must be bijective per owner')
        seen_alias.add((n,old)); seen_target.add((n,new)); row['selected_source_ids'][index] = new
    row = result['proposals'][5]; formula = design['one_comma_omission']
    _require(row['number'] == 87 and row['proposed_sutra'] == BEFORE
        and formula['json_pointer'] == '/proposals/5/proposed_sutra' and formula['number'] == 87
        and formula['before_exact'] == BEFORE and formula['after_exact'] == AFTER
        and formula['before_utf8_sha256'] == _text_hash(BEFORE) and formula['after_utf8_sha256'] == _text_hash(AFTER)
        and formula['codepoint_offset_zero_based'] == 11 and formula['codepoint_span_half_open'] == [11,12]
        and formula['utf8_byte_span_half_open'] == [31,32] and BEFORE.count(',') == 1
        and BEFORE[11] == ',' and BEFORE[:11]+BEFORE[12:] == AFTER, 'Only exact approved single comma omission allowed')
    _require([w.strip(',') for w in BEFORE.split()] == AFTER.split()
        and all(_devanagari_word(w) for w in AFTER.split()), 'Formula word/order/script changed')
    row['proposed_sutra'] = AFTER
    changes = _changes(native,result)
    _require(len(changes) == 4 and {c['json_pointer'] for c in changes} == PATHS
        and changes == design['all_changed_json_leaves_exact'], 'Exact four-leaf equality proof changed')
    _require(digest(result) == DERIVED_HASH == design['prospective_canonical_parsed_sha256'], 'Derived whole-answer hash drift')
    request = {'scope':'batch','entry_numbers':NUMBERS,'source_first_selection':SOURCE_FIRST_SELECTION,'sources_by_entry':packets}
    _check_answer('proposal','sutrakar',result,request); selection.validate_metadata(result,packets)
    for p in result['proposals']:
        if p['decision'] == 'ACCEPT':
            _require(all(_devanagari_word(w) for w in p['proposed_sutra'].split()), 'Mixed/Latin formula script forbidden')
    return result


def prepare_receipt(design_path, design_sha256, approval_path, approval_sha256):
    """Rebuild exact latest native, four changes, failed history and SDK proofs read-only.

    Returns deterministic receipt; never calls models or mutates a stage. Current
    source, hashes, independent design, dispatch completeness or witnesses may
    not drift. Fresh later peer stages do not replace the original twelve rounds.
    """
    from scripts import run_source_first_selection as selection
    from src.orchestration import source_peer_evidence as peer
    from src.orchestration.source_first_provider import parse_saved_response
    design_ref = reference(design_path,design_sha256); approval_ref = reference(approval_path,approval_sha256)
    design = read_bound(design_ref); approval = read_bound(approval_ref); target = design['target']; bindings = design['original_bindings']
    _require(design.get('schema') == 'source-first-exact-owned-id-and-one-comma-omission-design-v1'
        and approval.get('schema') == 'source-82-91-comma-alias-mechanical-independent-review-v1'
        and approval.get('gate') == 'PASS_MECHANICAL_DESIGN_ONLY', 'Exact independent mechanical-design approval required')
    name = 'selection-'+'-'.join(map(str,NUMBERS))
    _require(target['batch'] == name and target['stage'] == 'proposal' and target['speaker'] == 'sutrakar'
        and target['latest_attempt'] == 2 and target['core_request_sha256'] == FAILED_CORE, 'Only exact latest82..91 proposal scope allowed')
    dbpath = Path(target['council_db']).resolve(); source = dbpath.parent; provider = source/'provider'
    supplied = read_bound(bindings['input']); policy = read_bound(bindings['policy']); manifest = read_bound(bindings['manifest'])
    _require(Path(bindings['input']['path']).resolve().parent.samefile(source)
        and policy['batch_id'] == name and policy['numbers'] == NUMBERS and supplied['source_peer_policy'] == policy['policy'],
        'Original source root/policy drift')
    peer.validate_policy(policy['policy'],NUMBERS)
    # The original first-batch ledger is bound by the known full core hash.
    forbidden_path = source/'selection-1-discussion.json'
    forbidden = json.loads(forbidden_path.read_text(encoding='utf-8'))['discussion']['_batch']['forbidden_originals']
    with _ro(dbpath) as db:
        db.row_factory = sqlite3.Row
        attempts = [dict(r) for r in db.execute('SELECT * FROM research_attempts WHERE number=? AND stage=? AND speaker=? ORDER BY attempt',KEY)]
        stages = [dict(r) for r in db.execute("SELECT * FROM research_stages WHERE number=0 AND stage IN ('position','challenge','reply') ORDER BY stage,speaker")]
        installed_stage = db.execute('SELECT 1 FROM research_stages WHERE number=? AND stage=? AND speaker=?',KEY).fetchone()
        table = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(TABLE,)).fetchone()
        installed_authority = db.execute('SELECT 1 FROM '+TABLE+' WHERE number=? AND stage=? AND speaker=?',KEY).fetchone() if table else None
        _require(bool(installed_stage) == bool(installed_authority),'Incomplete existing proposal authority')
        first_adoption = installed_stage is None
        if first_adoption:
            _require(not db.execute("SELECT 1 FROM research_attempts WHERE stage='peer_review'").fetchone()
                and not db.execute("SELECT 1 FROM research_stages WHERE stage='peer_review'").fetchone(),
                'First adoption forbids pre-existing peer activity')
    _require(attempts == bindings['failed_attempts_exact'] and len(attempts) == 2
        and [a['attempt'] for a in attempts] == [1,2]
        and all(a['state'] == 'FAILED' and a['error'] == ERROR and a['response_json'] == 'null' for a in attempts),
        'Both original FAILED/null attempts must remain intact')
    siblings = [{'stage':r['stage'],'speaker':r['speaker'],'request_hash':r['request_hash'],
        'response_json_sha256':_text_hash(r['response_json'])} for r in stages]
    _require(siblings == bindings['cached12_stages'] and len(stages) == 12
        and {(r['stage'],r['speaker']) for r in stages} == {(st,v) for st in ('position','challenge','reply') for v in VOICES},
        'Original twelve paid rounds drift')
    core = {'number':0,'brief':{'batch_id':name},'sources':supplied['source_packets'],'scope':'batch','batch_id':name,
        'briefs':supplied['briefs'],'entry_numbers':NUMBERS,'sources_by_entry':supplied['source_packets'],
        'prior_formulas':supplied['prior_formulas'],'forbidden_originals':forbidden,'used_case_ids':[],
        'source_first_selection':SOURCE_FIRST_SELECTION,'source_peer_policy':policy['policy'],
        'discussion':{st:{r['speaker']:json.loads(r['response_json']) for r in stages if r['stage']==st} for st in ('position','challenge','reply')},
        'speaker':'sutrakar','stage':'proposal'}
    core_hash = _text_hash(_json(core))
    _require(core_hash == FAILED_CORE and all(a['request_hash'] == core_hash for a in attempts), 'Original core binding changed')
    with _ro(provider/'boundary.db') as db:
        db.row_factory = sqlite3.Row; config = db.execute('SELECT digest FROM config').fetchone()[0]
        if first_adoption:
            peer_slots = [digest([voice,'batch/'+name+'/peer_review'+suffix])
                for voice in VOICES[:-1] for suffix in ('','/schema-correction')]
            _require(not any(db.execute('SELECT 1 FROM calls WHERE slot=?',(slot,)).fetchone() for slot in peer_slots),
                'First adoption forbids pre-existing provider peer slots')
        calls = []
        for suffix in ('','/schema-correction'):
            row = db.execute('SELECT * FROM calls WHERE slot=?',(digest(['sutrakar','batch/'+name+'/proposal'+suffix]),)).fetchone()
            _require(row is not None,'Original actual proposal call missing'); calls.append(dict(row))
    with _ro(provider/'dispatch.db') as db:
        audits = [{'call_id':k,'record':json.loads(v)} for k,v in db.execute('SELECT call_id,record_json FROM council_dispatch_audit')]
    dispatch = []; documents = []
    for index, call in enumerate(calls):
        rawpath = provider/'raw'/(call['slot']+'.txt'); raw = rawpath.read_bytes(); native = json.loads(call['result_json'])
        _require(call['status'] == 'SUCCESS' and byte_hash(rawpath) == call['raw_sha256']
            and parse_saved_response(provider,call['slot'],raw) == native
            and digest(native) == call['result_sha256'] and call['source_sha256'] == digest(manifest['binding']),
            'Original native/provider/raw/source proof drift')
        requestpath = source/'peer-evidence'/(call['slot']+'-request.json'); document = json.loads(requestpath.read_text(encoding='utf-8'))
        callback = deepcopy(core)
        if index:
            callback.update(repair_feedback=attempts[0]['error'],previous_invalid_response=None,
                instruction='Correct the schema error; return a complete dictionary. Review only literal evidence in the current target.')
        rendered = peer.render('sutrakar',callback)
        _require(document == {'voice':'sutrakar','stage':'batch/'+name+'/proposal'+('/schema-correction' if index else ''),
            **rendered,'max_output_tokens':9000}
            and digest({**document,'config':config,'sources':call['source_sha256']}) == call['request_sha256'], 'Actual paid request reconstruction drift')
        found = [a for a in audits if a['record'].get('response_sha256') == call['raw_sha256']]
        _require(len(found) == 1 and found[0]['record'].get('status') == 'SUCCESS'
            and found[0]['record'].get('role') == selection.MODELS['sutrakar'][0]
            and found[0]['record'].get('provider') == selection.PROVIDERS['sutrakar']
            and found[0]['record'].get('model_id') == selection.MODELS['sutrakar'][1]
            and not found[0]['record'].get('was_truncated')
            and found[0]['record'].get('finish_reason') not in ('max_tokens','length','MAX_TOKENS'), 'Complete actual SDK audit required')
        dispatch.append(found[0]); documents.append(reference(requestpath,byte_hash(requestpath)))
    latest = calls[1]; native = json.loads(latest['result_json']); chosen = approval['chosen_latest_response']
    _require(latest == bindings['latest_provider_row'] and latest['slot'] == target['latest_provider_slot']
        and reference(provider/'raw'/(latest['slot']+'.txt'),latest['raw_sha256']) == bindings['latest_raw']
        and documents[1] == bindings['latest_request_document']
        and chosen['attempt'] == 2 and chosen['provider_slot'] == latest['slot']
        and chosen['request_sha256'] == latest['request_sha256'] and chosen['source_sha256'] == latest['source_sha256']
        and chosen['raw'] == bindings['latest_raw'] and chosen['provider_result_sha256'] == NATIVE_HASH
        and chosen['native_canonical_sha256'] == _text_hash(_json(native)), 'Independent latest/native request binding drift')
    canonical = transform(native,supplied['source_packets'],design)
    _require(approval['expected_derived_response_canonical_sha256'] == _text_hash(_json(canonical)), 'Independent complete derivative hash mismatch')
    mappings = approval['exact_alias_mapping']
    _require(len(mappings) == 3 and {(m['number'],m['index'],m['alias'],m['canonical_id']) for m in mappings} ==
        {(w['number'],int(w['json_pointer'].split('/')[-1]),w['from'],w['to']) for w in design['exact_alias_witnesses']}, 'Independent alias scope mismatch')
    operation = approval['single_format_operation']
    _require(operation['number'] == 87 and operation['field'] == 'proposed_sutra' and operation['before'] == BEFORE
        and operation['after'] == AFTER and operation['deleted_character'] == ','
        and operation['original_character_offset_zero_based'] == 11 and operation['deletion_count'] == 1,
        'Independent single separator operation mismatch')
    return {'kind':KIND,'design':design_ref,'approval':approval_ref,'source_dir':str(source),'council_db':str(dbpath),
        'core_request_sha256':core_hash,'original_attempts':attempts,'original_rounds':siblings,
        'original_exclusion_document':reference(forbidden_path,byte_hash(forbidden_path)),
        'original_provider_calls':calls,'original_dispatch':dispatch,'original_request_documents':documents,
        'original_native_sha256':digest(native),'canonical_answer':canonical,'canonical_answer_sha256':digest(canonical),
        'exact_changes':_changes(native,canonical),'all_other_fields_unchanged':True,
        'paid_calls':0,'peer_reviews_still_required':3,'bulk_source_resume_authorized':False}


def verify_receipt(path, expected_sha256):
    """Rebuild exact original+derived proofs on every receipt and stage replay."""
    receipt = read_bound(reference(path,expected_sha256))
    _require(receipt.get('kind') == KIND,'Typed exact proposal recovery receipt required')
    rebuilt = prepare_receipt(receipt['design']['path'],receipt['design']['sha256'],receipt['approval']['path'],receipt['approval']['sha256'])
    _require(receipt == rebuilt,'Proposal recovery receipt/proof drift')
    with _ro(receipt['council_db']) as db:
        stage = db.execute('SELECT request_hash,response_json FROM research_stages WHERE number=? AND stage=? AND speaker=?',KEY).fetchone()
        exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(TABLE,)).fetchone()
        authority = db.execute('SELECT request_hash,receipt_path,receipt_sha256 FROM '+TABLE+' WHERE number=? AND stage=? AND speaker=?',KEY).fetchone() if exists else None
    if stage or authority:
        pointer = reference(path,expected_sha256)
        _require(stage == (FAILED_CORE,_json({**receipt['canonical_answer'],MARKER:pointer}))
            and authority == (FAILED_CORE,pointer['path'],expected_sha256),'Adopted proposal/authority drift')
    return receipt,deepcopy(receipt['canonical_answer'])


def verify_cached_stage(dbpath, db, key, request_hash, saved):
    """Require exact authority even if marker/table/history are removed for known core."""
    exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(TABLE,)).fetchone()
    authority = db.execute('SELECT request_hash,receipt_path,receipt_sha256 FROM '+TABLE+' WHERE number=? AND stage=? AND speaker=?',key).fetchone() if exists else None
    if not (authority or MARKER in saved or request_hash == FAILED_CORE):return
    _require(key == KEY and request_hash == FAILED_CORE and authority is not None and MARKER in saved,
        'Mandatory exact proposal recovery authority missing')
    _require(authority[0] == request_hash and saved[MARKER] == {'path':authority[1],'sha256':authority[2]}, 'Proposal authority pointer drift')
    receipt,answer = verify_receipt(authority[1],authority[2])
    _require(Path(receipt['council_db']).samefile(dbpath) and saved == {**answer,MARKER:saved[MARKER]}, 'Foreign proposal authority/cache')


def require_adopted_known_stage(request_hash):
    """Stop the known spent request before attempts/callbacks if its stage is absent."""
    _require(request_hash != FAILED_CORE, 'Known failed proposal requires explicit adopted receipt; no callback or history recreation')


def _adopt_locked(path, sha):
    """Insert only missing canonical stage+authority under parent operator lock/gate."""
    receipt,answer = verify_receipt(path,sha); pointer = reference(path,sha)
    expected = (FAILED_CORE,_json({**answer,MARKER:pointer}))
    with sqlite3.connect(receipt['council_db']) as db:
        db.execute('BEGIN IMMEDIATE');verify_receipt(path,sha)
        stage = db.execute('SELECT request_hash,response_json FROM research_stages WHERE number=? AND stage=? AND speaker=?',KEY).fetchone()
        _require(stage is None or stage == expected,'Conflicting proposal stage')
        db.execute('CREATE TABLE IF NOT EXISTS '+TABLE+'(number INTEGER,stage TEXT,speaker TEXT,request_hash TEXT NOT NULL,receipt_path TEXT NOT NULL,receipt_sha256 TEXT NOT NULL,PRIMARY KEY(number,stage,speaker))')
        old = db.execute('SELECT request_hash,receipt_path,receipt_sha256 FROM '+TABLE+' WHERE number=? AND stage=? AND speaker=?',KEY).fetchone()
        authority = (FAILED_CORE,pointer['path'],sha)
        _require((stage is None and old is None) or (stage == expected and old == authority),'Conflicting/incomplete proposal authority')
        db.execute('INSERT OR IGNORE INTO '+TABLE+' VALUES (?,?,?,?,?,?)',(*KEY,*authority))
        db.execute('INSERT OR IGNORE INTO research_stages VALUES (?,?,?,?,?)',(*KEY,*expected))
        verify_cached_stage(receipt['council_db'],db,KEY,FAILED_CORE,{**answer,MARKER:pointer})
    return {'status':'EXACT_PROPOSAL_ADOPTED','receipt':pointer,'entry_numbers':NUMBERS,'paid_calls':0,
        'peer_reviews_still_required':3,'bulk_source_resume_authorized':False}
