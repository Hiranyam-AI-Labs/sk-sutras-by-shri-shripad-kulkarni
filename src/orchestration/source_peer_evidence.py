"""Opt-in future source-peer field IDs and row-local literal constraints.

Default/legacy requests never enter this adapter. There is no provider factory,
quote repair, semantic scoring or added council round. Raw SDK opinions remain
immutable; field-ID replies acquire exact current quotes only on the server.
"""
from copy import deepcopy
import hashlib
import json
import re
from pathlib import Path
import sqlite3

from src.orchestration.source_first_partial_completion import _ro, _require, digest
from src.orchestration.research_acceptance import _normalize_formula
from src.orchestration.research_council import _json, _check_answer

VERSION='source-selection-evidence-menu-v1'
REFERENCE_VERSION='source-selection-reference-menu-v2'
VERSIONS=(VERSION,REFERENCE_VERSION)
KEY='source_peer_policy'
NATIVE='_source_peer_native'
MAPPING='source_peer_evidence_selection'
SYSTEM_APPEND='\nFUTURE SOURCE INPUT POLICY: Only supplied prior_accepted_decisions are actual historical\nbusiness-decision comparators. Old formula and HOLD history is not supplied;\nno inference from an absent list is evidence of duplication. Shared devotional\nthemes are legitimate inspiration. Compare material condition/action and the\nactual current batch. Complementary passages need not repeat identical definitions\nor literally mention business. Preserve source limits, constructive Sutrakar\nownership and genuine REJECT. Literal formula exclusions are enforced server-side.\nPeer issues select existing current-proposal evidence IDs; never generate quotes.\n'
HISTORY_KEYS={'forbidden_originals','literal_formula_exclusions','prior_formulas',
    'held_selection_decisions','selection_history','prior_accepted_decisions','_batch',NATIVE,
    'exact_proposal_recovery'}


def read_bound(ref):
    """Read an explicit current immutable document; drift fails before SDK access."""
    _require(isinstance(ref,dict) and set(ref)=={'path','sha256'},'Explicit committed path/SHA required')
    raw=Path(ref['path']).read_bytes()
    _require(hashlib.sha256(raw).hexdigest()==ref['sha256'],'Committed document hash drift')
    return json.loads(raw.decode('utf-8'))


def committed(refs):
    """Load parent-declared actual READY results or accepted canonical proposals.

    Returns compact decision/action cards, literal formulas and proof bindings.
    HOLD/REJECT, duplicate owners, missing source discussion or peer PASS fail.
    This does not allocate cases or turn source acceptance into a READY chapter.
    """
    from scripts import run_source_first_selection as s
    from scripts import export_source_first_book as export
    from src.orchestration.source_first_case_capsule import _selection
    _require(isinstance(refs,list),'Explicit committed reference list required, including []')
    cards=[];formulas=[];proofs=[];seen=set();numbers=set()
    for ref in refs:
        doc=read_bound(ref);p=Path(ref['path']);path=p if p.is_absolute() else p.resolve()
        if doc.get('status')=='ACCEPTED_FOR_CASE_ASSIGNMENT':
            _require(doc.get('case_curation_eligible') is True,'Committed candidate must be genuinely eligible')
            discussion_path=path.parent/doc['discussion_file'];bundle=json.loads(discussion_path.read_text(encoding='utf-8'))
            _require(hashlib.sha256(discussion_path.read_bytes()).hexdigest()==doc['discussion_sha256'],'Committed discussion drift')
            ip=path.parent/doc['discussion_file'].replace('-discussion.json','-input.json');supplied=json.loads(ip.read_text(encoding='utf-8'))
            number=doc['number'];brief=next(b for b in supplied['briefs'] if b['number']==number);packet=supplied['source_packets'][str(number)]
            checked=_selection(number,brief,packet,bundle['discussion'],bundle['proposal'],bundle['peer_review'])
            proposal=next(p for p in bundle['proposal']['proposals'] if p['number']==number)
            peers={v:next(r for r in rows['reviews'] if r['number']==number) for v,rows in bundle['peer_review'].items()}
            _require(doc['proposal']==proposal and doc['peer_review']==peers and doc['candidate_id']==brief['candidate_id']
                and doc['selection_entry_hash']==checked['original_entry_sha256'] and doc['source_packet_sha256']==digest(packet)
                and s.rebuild_source_packet(packet)==packet,'Canonical committed candidate proof drift')
            _require(supplied['prior_formulas']==bundle['discussion']['_batch']['prior_formulas'],'Committed input/history drift')
            owner=doc['candidate_id'];formula=proposal['proposed_sutra']
            extra={'input':{'path':str(ip),'sha256':hashlib.sha256(ip.read_bytes()).hexdigest()},
                'discussion':{'path':str(discussion_path),'sha256':doc['discussion_sha256']},'kind':'accepted_source_decision'}
        else:
            draft,proposal,_=export._eligible(doc)
            _require(draft['id'].startswith('source-selection-'),'Only this source-first book supplies committed results')
            owner=draft['id'].removeprefix('source-selection-');number=draft['number'];formula=draft['new_sutra'];extra={'kind':'ready_result'}
        _require(proposal.get('decision')=='ACCEPT' and type(number) is int and number>0
            and re.fullmatch(r'N[0-9]{3}-S[0-9]{3}',owner) is not None
            and owner not in seen and number not in numbers,'Only unique actual committed ACCEPT decisions allowed')
        _require(all(isinstance(proposal.get(k),str) and proposal[k].strip() for k in ('business_decision_mr','business_action_mr')),'Actual committed decision/action required')
        seen.add(owner);numbers.add(number)
        cards.append({'id':owner,'number':number,'business_decision_mr':proposal['business_decision_mr'],'business_action_mr':proposal['business_action_mr']})
        formulas.append(formula);proofs.append({'reference':{'path':str(path),'sha256':ref['sha256']},**extra})
    return cards,formulas,proofs


def make_policy(refs,*,version=VERSION):
    """Freeze actual parent-declared cards/proofs; never infer commitments from history."""
    _require(version in VERSIONS,'Unknown future peer policy')
    cards,formulas,proofs=committed(refs)
    policy={'version':version,'committed_references':[p['reference'] for p in proofs],
        'committed_cards':cards,'committed_formulas':formulas,'provenance':proofs}
    return {**policy,'policy_sha256':digest(policy)}


def validate_policy(policy,numbers):
    """Validate a wholly future batch and frozen actual comparison inputs read-only."""
    _require(isinstance(policy,dict) and policy.get('version') in VERSIONS and numbers,
        'Known explicit future peer policy required')
    minimum=92 if policy['version']==REFERENCE_VERSION else 82
    _require(all(type(n) is int and minimum<=n<=124 for n in numbers),
        'Reference v2 is only for92..124; evidence v1 only for82..124')
    _require(policy==make_policy(policy['committed_references'],version=policy['version']),'Frozen committed policy/card proof drift')
    _require(not(set(numbers)&{c['number'] for c in policy['committed_cards']}),'Current-batch entry cannot masquerade as prior commitment')
    return policy


def assert_unstarted(work,batch_id):
    """Reject any old paid/core/input state before opting a new batch into the policy."""
    work=Path(work)
    _require(not (work/(batch_id+'-input.json')).exists(),'Cannot opt in an already started input batch')
    dbpath=work/('council.db.batch-'+hashlib.sha256(_json(batch_id).encode()).hexdigest()+'.sqlite3')
    if dbpath.exists():
        with _ro(dbpath) as db:
            _require(all(db.execute('SELECT count(*) FROM '+table).fetchone()[0]==0 for table in ('research_runs','research_attempts','research_stages')),'Cannot change a started council batch policy')
    dbpath=work/'provider/boundary.db'
    if dbpath.exists():
        slots=[digest([v,f'batch/{batch_id}/{stage}'+suffix]) for stage,voices in
            [('position',('narada','shandilya','researcher','sutrakar')),('challenge',('narada','shandilya','researcher','sutrakar')),
             ('reply',('narada','shandilya','researcher','sutrakar')),('proposal',('sutrakar',)),('peer_review',('narada','shandilya','researcher'))]
            for v in voices for suffix in ('','/schema-correction')]
        with _ro(dbpath) as db:_require(not any(db.execute('SELECT 1 FROM calls WHERE slot=?',(slot,)).fetchone() for slot in slots),'Cannot opt in any existing paid slot')


def batch_policy(work,batch_id,numbers,requested,refs,*,create=False):
    """Read exact frozen policy on resume; only new batches use newly supplied cards.

    No output is written for preflight. Legacy batches/defaults remain unchanged.
    A partly paid batch cannot switch protocol; changed supplied cards affect only
    subsequent wholly unstarted batches, never old paid request identities.
    """
    from scripts import run_source_first_selection as s
    _require(requested is None or requested in VERSIONS,'Unknown future peer policy')
    path=Path(work)/(batch_id+'-peer-policy.json')
    if path.exists():
        saved=json.loads(path.read_text(encoding='utf-8'))
        _require(saved.get('batch_id')==batch_id and saved.get('numbers')==numbers,'Frozen batch policy scope drift')
        return validate_policy(saved['policy'],numbers)
    if min(numbers)<82:return None
    if requested is None:
        _require(not list(Path(work).glob('*-peer-policy.json')),'Explicit future policy required for another new batch')
        return None
    assert_unstarted(work,batch_id);policy=validate_policy(make_policy(refs,version=requested),numbers)
    if create:s.book.save_checkpoint(path,{'batch_id':batch_id,'numbers':numbers,'policy':policy})
    return policy


def _strip_history(value):
    """Remove historical/audit structures by key; keep all current text byte-for-byte."""
    if isinstance(value,dict):return {k:_strip_history(v) for k,v in value.items() if k not in HISTORY_KEYS}
    if isinstance(value,list):return [_strip_history(v) for v in value]
    return deepcopy(value)


def catalog(request):
    """Build whole-field mnemonic IDs bound to full request/proposal and owning entry."""
    validate_policy(request[KEY],request['entry_numbers'])
    entries={p['number']:p for p in request['proposal']['proposals']}
    _require(set(entries)==set(request['entry_numbers']) and len(entries)==len(request['proposal']['proposals']),'Exact proposal coverage for evidence menu required')
    fields={}
    for number in request['entry_numbers']:
        for field,value in sorted(entries[number].items()):
            leaves=[(field,value)] if isinstance(value,str) else [(f'{field}.{i}',v) for i,v in enumerate(value) if isinstance(v,str)] if isinstance(value,list) else []
            for path,text in leaves:
                ident=f'P{number:03d}.{path}'
                _require(ident not in fields,'Evidence ID collision')
                fields[ident]={'number':number,'field':path,'text':text}
    value={'request_sha256':hashlib.sha256(_json(request).encode()).hexdigest(),
        'proposal_sha256':digest(request['proposal']),'policy_sha256':request[KEY]['policy_sha256'],'fields':fields}
    return {**value,'menu_sha256':digest(value)}


def reference_menu(request):
    """Bind each entry's allowed canonical IDs, not researcher component aliases.

    Packets have already passed the unchanged research/source preflight. This
    menu selects only their existing reference IDs; it adds no source or proof.
    The full packet hashes retain all source/verification provenance server-side.
    """
    policy=validate_policy(request[KEY],request['entry_numbers'])
    _require(policy['version']==REFERENCE_VERSION,'Canonical reference menu requires v2')
    packets=request.get('sources_by_entry',request['sources'])
    _require(isinstance(packets,dict) and set(packets)=={str(n) for n in request['entry_numbers']}
        and len(set(request['entry_numbers']))==len(request['entry_numbers']),
        'Canonical reference menu requires exact entry ownership')
    if 'sources_by_entry' in request:
        _require(packets==request['sources'],'Canonical source views disagree')
    entries={}
    for number in request['entry_numbers']:
        packet=packets[str(number)];pair=packet.get('source_pair_ids');refs=packet.get('references')
        _require(isinstance(pair,list) and len(pair)==2 and all(isinstance(i,str) for i in pair)
            and re.fullmatch(r'N[0-9]+',pair[0]) is not None
            and re.fullmatch(r'S[0-9]+',pair[1]) is not None
            and isinstance(refs,list) and all(isinstance(r,dict) and isinstance(r.get('id'),str) for r in refs),
            'Canonical Narada/Shandilya pair and existing reference records required')
        ids=[r['id'] for r in refs]
        _require(len(ids)==len(set(ids)) and set(pair).issubset(ids)
            and all(i and '::' not in i for i in ids),'Canonical reference IDs must be unique and unambiguous')
        supplementary=[i for i in ids if i not in pair]
        _require(supplementary,'Existing supplementary reference required')
        entries[str(number)]={'number':number,'required_source_pair_ids':deepcopy(pair),
            'allowed_reference_ids':ids,'supplementary_reference_ids':supplementary,
            'source_packet_sha256':digest(packet),'reference_records_sha256':digest(refs)}
    value={'version':REFERENCE_VERSION,'policy_sha256':policy['policy_sha256'],'entries':entries}
    return {**value,'menu_sha256':digest(value)}


def _reference_view(view):
    """Omit competing provenance ID labels only; retain every substantive value.

    Current discussion/proposal opinions are never redacted or canonicalized.
    This operates only on the detached v2 model-view copy, never source packets.
    """
    for packet in view['sources'].values():
        research=packet.get('research_interpretation',{})
        ids=research.get('evidence_ids')
        if isinstance(ids,list):
            kept=[i for i in ids if not (isinstance(i,str) and '::' in i)]
            if kept:research['evidence_ids']=kept
            else:research.pop('evidence_ids',None)
        for context in packet.get('source_contexts',{}).values():
            if isinstance(context,dict) and isinstance(context.get('id'),str) and '::' in context['id']:
                context.pop('id')
    return view


def render(voice,request):
    """Render only opted-in source requests; legacy renderer/system are never changed."""
    from scripts import run_source_first_selection as s
    _require(voice==request['speaker'] and voice in ('narada','shandilya','researcher','sutrakar'),'Current source voice ownership required')
    policy=validate_policy(request[KEY],request['entry_numbers'])
    view=s.writing_view(request);view[KEY]={'version':policy['version'],'policy_sha256':policy['policy_sha256']}
    view=_strip_history(view);view['prior_accepted_decisions']=deepcopy(policy['committed_cards']);view['role_focus']=s.ROLE_FOCUS[voice]
    if policy['version']==REFERENCE_VERSION:
        view=_reference_view(view);view['canonical_reference_menu']=reference_menu(request)
    if request['stage']=='peer_review':
        menu=catalog(request)
        view['proposal_evidence_menu']={'binding_sha256':menu['menu_sha256'],'items':[{'id':i,'number':r['number'],'field':r['field']} for i,r in menu['fields'].items()]}
        instruction=("Return {reviews:[{number,verdict:'PASS'|'REVIEW_REQUIRED',issues:[{evidence_id,reason,severity}]}]} for EXACTLY every entry number "
            +str(request['entry_numbers'])+". Select only that entry's current proposal-field ID from proposal_evidence_menu. Do not generate field or quote strings. PASS requires issues:[]. Preserve your own substantive source/grammar/metadata judgment; do not edit the proposal. Review REJECT reasons as strictly as ACCEPT; no formula is required for REJECT. Assess the strongest actual peer reply, genuine complementary supplementary support, qualified modern application, both canonical references and accepted business metadata. Neither identical definitions nor literal business language in ancient sources is required. Shared broad themes/HOLD history are not novelty vetoes. Historical duplication needs a supplied committed condition/action comparator; current-batch comparisons remain reasoned, without quota.")
    else:instruction=s.selection_contract(request['stage'],request)
    if policy['version']==REFERENCE_VERSION and request['stage']=='peer_review':
        view['current_formula_shapes']={}
        for proposal in request['proposal']['proposals']:
            if proposal.get('decision')!='ACCEPT':continue
            formula=proposal['proposed_sutra'];counted=formula.strip().strip('।॥').strip()
            view['current_formula_shapes'][str(proposal['number'])]={'formula_exact':formula,
                'counted_text':counted,'word_count':len(re.findall(r'[^\s।॥]+',counted)),
                'unicode_character_count':len(counted),'grammar_approval':False}
        instruction+=(" current_formula_shapes supplies deterministic existing-gate counts ONLY, NOT grammar approval. "
            "Read the WHOLE current field and current derivation/limits before asserting anything is missing. "
            "An already explicit modern-analogy label is not itself an issue: if inadequate, identify the remaining false or unsupported claim. "
            "Absence of ancient hiring/business vocabulary alone cannot veto a bounded qualified analogy. "
            "A grammar objection must identify a concrete erroneous form, sandhi, agreement or construction, not merely 'confirm' or 'awkward'. "
            "Assess the short formula with its derivation; do not demand all qualifications inside its2–4words. "
            "Retain genuine source-fidelity, grammar and practical-risk objections, including unsupported mandatory-sutra claims; no acceptance waiver.")
    if policy['version']==REFERENCE_VERSION and request['stage']=='proposal':
        instruction+=(" For each ACCEPT, selected_source_ids must use ONLY that entry's "
            "canonical_reference_menu allowed_reference_ids: include EXACTLY BOTH "
            "required_source_pair_ids and at least one defensible existing supplementary_reference_id. "
            "Choose the verified supplied subset that actually supports your derivation; the menu "
            "is not a reason to force acceptance. Use canonical reference IDs, never pair::component "
            "provenance IDs. proposed_sutra must remain one short formula of 2–4 words and "
            "at most32Unicodecharacters, without a comma (including ，) or compound-sentence format. "
            "No new response fields, source quotations or automatic formula repair.")
    return {'system':s.SELECTION_SYSTEM+'\nROLE FOCUS: '+s.ROLE_FOCUS[voice]+SYSTEM_APPEND,
        'payload':{'instruction':instruction,'input':view}}


def materialize(native,request,binding):
    """Select exact current field text under server request/menu provenance only.

    Raw votes/reasons/severities remain unchanged. Cross-entry/stale/unknown IDs,
    quote injection and coverage errors fail; no fuzzy fallback or new verdict.
    """
    menu=catalog(request)
    _require(binding=={k:menu[k] for k in ('request_sha256','proposal_sha256','menu_sha256')},'Stale evidence request/menu binding')
    _require(isinstance(native,dict) and set(native)=={'reviews'} and isinstance(native['reviews'],list),'Reference-only peer response required')
    reviews=[];seen=set();mapping=[]
    for row in native['reviews']:
        _require(isinstance(row,dict) and set(row)=={'number','verdict','issues'} and type(row['number']) is int and row['number'] not in seen and row['number'] in request['entry_numbers'],'Exact peer entry ownership required')
        _require(isinstance(row['issues'],list),'Peer issues must be a list');seen.add(row['number']);issues=[]
        for index,issue in enumerate(row['issues']):
            _require(isinstance(issue,dict) and set(issue)=={'evidence_id','reason','severity'},'Generated field/quote or unexpected issue keys prohibited')
            selected=menu['fields'].get(issue['evidence_id']) if isinstance(issue['evidence_id'],str) else None
            _require(selected is not None and selected['number']==row['number'],'Unknown or cross-entry evidence ID')
            issues.append({'field':selected['field'],'quote':selected['text'],'reason':issue['reason'],'severity':issue['severity']})
            mapping.append({'number':row['number'],'issue_index':index,'evidence_id':issue['evidence_id'],'field':selected['field'],'text_sha256':hashlib.sha256(selected['text'].encode()).hexdigest()})
        reviews.append({'number':row['number'],'verdict':row['verdict'],'issues':issues})
    _require(seen==set(request['entry_numbers']),'Complete peer review coverage required')
    canonical={'reviews':reviews};_check_answer('peer_review',request['speaker'],canonical,request)
    return canonical,mapping


def _callback_request(dbpath,request,attempt):
    """Rebuild the existing bounded schema-correction context for exact raw replay."""
    _require(type(attempt) is int and attempt in (1,2),'Only existing two-attempt peer protocol allowed')
    payload=deepcopy(request)
    if attempt>1:
        with _ro(dbpath) as db:
            row=db.execute('SELECT state,error,response_json FROM research_attempts WHERE number=? AND stage=? AND speaker=? AND attempt=?',
                (request['number'],request['stage'],request['speaker'],attempt-1)).fetchone()
        _require(row and row[0]=='FAILED','Exact previous bounded failure required')
        payload.update(repair_feedback=row[1],previous_invalid_response=json.loads(row[2]),
            instruction='Correct the schema error; return a complete dictionary. Review only literal evidence in the current target.')
    return payload


def _build_mapping(dbpath,request,callback,wrapper,attempt):
    """Bind native SDK bytes, actual model request and current menu; no file writes."""
    from src.orchestration.source_first_provider import parse_saved_response
    _require(isinstance(wrapper,dict) and NATIVE in wrapper,'Mandatory native peer request proof required')
    meta=wrapper[NATIVE];native={k:v for k,v in wrapper.items() if k!=NATIVE}
    call=read_bound(meta['request_document']);root=Path(dbpath).parent;provider=root/'provider'
    _require(Path(meta['provider_work']).samefile(provider),'Foreign peer provider root')
    suffix='/schema-correction' if attempt>1 else '';stage=f"batch/{request['batch_id']}/peer_review"+suffix
    slot=digest([request['speaker'],stage]);_require(meta['slot']==slot and call['voice']==request['speaker'] and call['stage']==stage,'Wrong peer call/slot ownership')
    _require(callback==_callback_request(dbpath,request,attempt),'Stale callback context')
    expected=render(request['speaker'],callback)
    _require(call['system']==expected['system'] and call['payload']==expected['payload'],'Actual peer model view/menu drift')
    with _ro(provider/'boundary.db') as db:
        db.row_factory=sqlite3.Row;found=db.execute('SELECT * FROM calls WHERE slot=?',(slot,)).fetchone();config=db.execute('SELECT digest FROM config').fetchone()[0]
    _require(found is not None,'Actual native provider response missing');row=dict(found)
    actual={**call,'config':config,'sources':row['source_sha256']}
    _require(row['status']=='SUCCESS' and digest(actual)==row['request_sha256'],'Actual peer request hash mismatch')
    raw=(provider/'raw'/(slot+'.txt')).read_bytes()
    _require(hashlib.sha256(raw).hexdigest()==row['raw_sha256'] and parse_saved_response(provider,slot,raw)==native==json.loads(row['result_json'])
        and digest(native)==row['result_sha256'],'Native peer raw/result mismatch')
    menu=catalog(callback);binding={k:menu[k] for k in ('request_sha256','proposal_sha256','menu_sha256')}
    canonical,mapping=materialize(native,callback,binding)
    proof={'kind':request[KEY]['version'],'number':request['number'],'stage':request['stage'],'speaker':request['speaker'],'attempt':attempt,
        'core_request_sha256':hashlib.sha256(_json(request).encode()).hexdigest(),'binding':binding,
        'request_document':deepcopy(meta['request_document']),'provider_work':str(provider.resolve()),'provider_row':row,
        'mapping':mapping,'canonical_sha256':digest(canonical),'opinions_unchanged':True,'quotes_are_exact_server_selections':True}
    return proof,canonical


def materialize_stage(dbpath,request,callback,wrapper,attempt):
    """Persist deterministic mapping proof before normal council validation/commit."""
    from scripts import run_source_first_selection as s
    proof,canonical=_build_mapping(dbpath,request,callback,wrapper,attempt)
    path=Path(dbpath).parent/'peer-evidence'/(digest([request['speaker'],request['batch_id'],attempt])+'.json')
    s.book.save_checkpoint(path,proof)
    return {**canonical,MAPPING:{'path':str(path.resolve()),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}}


def verify_cached(dbpath,request,saved):
    """Require and rebuild raw-ID mapping on every new-policy peer cache replay."""
    _require(MAPPING in saved,'Mandatory source-peer mapping receipt missing')
    pointer=saved[MAPPING];proof=read_bound(pointer)
    _require(proof.get('kind')==request[KEY]['version'] and proof['core_request_sha256']==hashlib.sha256(_json(request).encode()).hexdigest(),'Stale peer mapping authority')
    attempt=proof['attempt']
    with _ro(dbpath) as db:
        row=db.execute('SELECT request_hash,state,response_json FROM research_attempts WHERE number=? AND stage=? AND speaker=? AND attempt=?',
            (request['number'],request['stage'],request['speaker'],attempt)).fetchone()
    _require(row and row[0]==proof['core_request_sha256'] and row[1]=='COMPLETE','Original successful native council attempt missing')
    callback=_callback_request(dbpath,request,attempt)
    rebuilt,canonical=_build_mapping(dbpath,request,callback,json.loads(row[2]),attempt)
    _require(rebuilt==proof and saved=={**canonical,MAPPING:pointer},'Raw-ID materialized peer cache drift')


def literal_constraints(proposals,prior,forbidden,policy):
    """Return entry-local objective copy holds; never edit opinions or stop a batch."""
    ledgers={'prior_formulas':prior,'forbidden_originals':forbidden,'committed_formulas':policy['committed_formulas']}
    result={}
    for p in proposals['proposals']:
        if p.get('decision')!='ACCEPT':continue
        formula=p['proposed_sutra'];matches=[]
        for name,items in ledgers.items():
            _require(isinstance(items,list) and all(isinstance(v,str) and v.strip() for v in items),'Literal ledger malformed')
            for index,value in enumerate(items):
                if _normalize_formula(formula)==_normalize_formula(value):
                    matches.append({'kind':'EXACT_NORMALIZED_FORMULA_COPY','ledger':name,'index':index,
                        'formula_sha256':hashlib.sha256(formula.encode()).hexdigest(),'matched_literal_sha256':hashlib.sha256(value.encode()).hexdigest()})
        if matches:result[str(p['number'])]=matches
    return result


def require_entry_clear(number,proposal,batch):
    """Block only a copied future proposal at case attachment, preserving all peers."""
    if KEY not in batch:return
    policy=validate_policy(batch[KEY],batch['entry_numbers'])
    holds=literal_constraints({'proposals':[proposal]},batch['prior_formulas'],batch['forbidden_originals'],policy)
    _require(str(number) not in holds,'Entry remains HOLD_SERVER_CONSTRAINT for exact literal formula copy')
