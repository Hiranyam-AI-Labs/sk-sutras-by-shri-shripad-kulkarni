"""Single saved HOLD revision: one Sutrakar proposal + three fresh peer reviews.

No old discussion call, fifth review, composition, source edit or gate change.
CLI defaults to read-only preflight. --live is explicit; --resume reuses exact
successful provider slots. --work must be a NEW short root (for example
logs/sf-revise-20261121). Failures are durable terminal stops, not retry loops.
An external current-code receipt must cover REQUIRED_TESTS. Previously passing
unchanged interfaces may be carried forward by the parent; this runner never
certifies its own code. Execution receipts are separate from cache identity.

Outputs retain the original input bytes and full three-round/_batch maps.
Only the selected proposal/reviews and resulting selected disposition change.
revision-provenance.json binds original artifacts and actual provider request,
raw-response and parsed-response hashes. result.json seals derived byte hashes.
The ordinary capsule/selected-book validators remain authoritative and unchanged.
"""
from copy import deepcopy
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3
import sys

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))
from scripts import run_source_first_selection as selection
from src.orchestration.research_council import VOICES, SOURCE_FIRST_SELECTION, _check_answer, _numbered, _json
from src.orchestration.source_first_provider import (
    SourceFirstProvider, SourceFirstStopped, create_live_provider, call_with_lossless_framing,
    _exclusive, _work_path, _hash as provider_hash,
)

load,save,byte_hash=selection.load,selection.save,selection.byte_hash
REQUIRED_TESTS=('tests/test_source_first_revision_runner.py','tests/test_source_first_revision_integration.py',
                'tests/test_source_first_selection_runner.py',
                'tests/test_source_first_case_capsule.py','tests/test_source_first_selected_book_runner.py')
POLICY={'version':'source-first-proposal-revision-v1','proposal_calls':1,'peer_calls':3,
        'max_calls':4,'timeout_seconds':240,'effort':'medium','tokens':4096,
        'json_framing':'single-extra-closing-brace-v1','schema_retry':False}
REVISION_SYSTEM=selection.SELECTION_SYSTEM+"""
SAVED-PROPOSAL REVISION ONLY. Reuse the completed original three rounds. The
original peer feedback quotes target original_proposal ONLY; fresh peer issues
must target the revised current proposal, not abandoned wording. Do not repeat
positions/challenges/replies, add sources, write chapters or call the validator.
Address every listed old issue, correcting a valid objection or substantively
contesting an invalid requirement. No requirement to cite every offered reference,
make different ethical lists identical, or repeat a modern-interpretation caveat
in every individual field if the complete proposal clearly distinguishes claims.
These permissions never excuse a forced link, ambiguous ethical principle,
false attribution or invented factual promise. Initial restraint AND its ongoing
observance may matter; assess the actual source. Selected supplementary sources
may be a defensible subset; both sutras and genuine supplementary support remain
mandatory for ACCEPT. Mechanical counts are deterministic facts, NOT grammar or
semantic certification. Never turn a valid shape count into a fabricated failure.
REJECT remains available with a substantive reason and no Sanskrit formula.
"""
PROPOSAL_EXTRA="""Return the existing proposals envelope for the ONE entry, plus a separate
revision_responses list: [{issue_id,disposition:'ADDRESSED'|'CONTESTED'|'CANDIDATE_REJECTED',reason_mr}].
Cover every supplied original issue_id exactly once. Explain concrete corrections
or source-specific reasons for contesting requirements; do not merely mark done.
The response table is revision audit metadata, not a new consumer proposal field.
"""
PEER_EXTRA="""Review ONLY the current revised proposal. Use the original issue response table
as context, not as proof that an issue is resolved. Anchor every new issue to an
exact current proposal field/quote. Do not require all offered references, identical
virtue lists or a disclaimer in every field. Use current_formula_shape for literal
counts, without inferring grammatical validity. PASS only after substantive review.
"""


def code_bindings():
    """Return exact execution/test seals; missing files fail before credentials."""
    paths=sorted({p for d in ('src','scripts') for p in (ROOT/d).rglob('*.py')}
                 |{ROOT/p for p in REQUIRED_TESTS}|{ROOT/p for p in selection.REQUIRED_TESTS})
    return {p.relative_to(ROOT).as_posix():byte_hash(p) for p in paths}


def require_gate(path):
    """Validate external current-code test evidence; return receipt or fail closed.

    Previous interface results are reusable only at their unchanged exact bytes.
    This function loads no key, creates no adapter and grants no paid permission.
    """
    gate=load(path);rows=gate.get('tests')
    if gate.get('status')!='PASS' or type(gate.get('paid_calls')) is not int or gate['paid_calls']!=0 or gate.get('code_sha256')!=code_bindings() or not isinstance(rows,list):
        raise ValueError('Current exact revision code/test gate required')
    for name in REQUIRED_TESTS:
        found=[r for r in rows if isinstance(r,dict) and r.get('path')==name]
        if len(found)!=1 or type(found[0].get('passed')) is not int or found[0]['passed']<1 or any(type(found[0].get(k)) is not int or found[0][k]!=0 for k in ('failed','errors')):
            raise ValueError('Required revision/interface regression missing: '+name)
    return gate


def formula_shape(proposal):
    """Return exact core-style counts without interpreting grammar or meaning."""
    formula=proposal.get('proposed_sutra')
    text=formula.strip().strip('।॥').strip() if isinstance(formula,str) else ''
    return {'formula':formula,'words':len(re.findall(r'[^\s।॥]+',text)),
            'unicode_characters':len(text),'grammar_certified':False}


def _read_bound(path,expected):
    """Read exact caller-bound JSON bytes; return data/raw/proof, never normalize."""
    path=Path(path).resolve();raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=expected:
        raise ValueError('Original artifact byte hash drift: '+path.name)
    return json.loads(raw.decode('utf-8-sig')),raw,{'path':str(path),'sha256':expected,'bytes':len(raw)}


def preflight(*,source_dir,number,candidate_sha256,input_sha256,discussion_sha256,offline_gate):
    """Validate the saved HOLD, all original maps and current code before keys.

    Return immutable revision context plus a separate current execution receipt.
    Invalid or mismatched source/proposal/peer records stop, never become PASS.
    """
    if type(number) is not int or number<1:raise ValueError('One positive logical number required')
    source=Path(source_dir).resolve()
    candidate,_,cp=_read_bound(source/f'candidate-{number:03d}.json',candidate_sha256)
    name=candidate.get('discussion_file')
    if not isinstance(name,str) or Path(name).name!=name or not re.fullmatch(r'selection-(?:\d+-)*\d+-discussion\.json',name):
        raise ValueError('Original discussion basename required')
    bundle,_,dp=_read_bound(source/name,discussion_sha256)
    input_name=name.replace('-discussion.json','-input.json')
    supplied,input_raw,ip=_read_bound(source/input_name,input_sha256)
    binding=bundle['discussion']['_batch'];numbers=binding['entry_numbers']
    briefs={b['number']:b for b in supplied['briefs']}
    if len(briefs)!=len(supplied['briefs']) or set(briefs)!=set(numbers) or number not in briefs or set(supplied['source_packets'])!={str(n) for n in numbers} or binding.get('source_first_selection')!=SOURCE_FIRST_SELECTION:
        raise ValueError('Original batch/brief/source coverage drift')
    for n in numbers:
        expected=hashlib.sha256(_json({'brief':briefs[n],'sources':supplied['source_packets'][str(n)]}).encode()).hexdigest()
        if binding['entry_hashes'].get(str(n))!=expected:raise ValueError('Original entry binding drift')
    if supplied['prior_formulas']!=binding['prior_formulas']:raise ValueError('Original prior formulas drift')
    request={'scope':'batch','entry_numbers':numbers,'source_first_selection':SOURCE_FIRST_SELECTION,
             'sources_by_entry':supplied['source_packets'],'proposal':bundle['proposal']}
    for stage in ('position','challenge','reply'):
        if set(bundle['discussion'][stage])!=set(VOICES):raise ValueError('All four original voices required')
        for voice,answer in bundle['discussion'][stage].items():_check_answer(stage,voice,answer,request)
    _check_answer('proposal','sutrakar',bundle['proposal'],request)
    if set(bundle['peer_review'])!=set(VOICES[:-1]):raise ValueError('Exactly three original reviews required')
    for voice,answer in bundle['peer_review'].items():_check_answer('peer_review',voice,answer,request)
    proposal=_numbered(bundle['proposal']['proposals'],numbers,'Original proposals')[number]
    peers={v:_numbered(b['reviews'],numbers,'Original reviews')[number] for v,b in bundle['peer_review'].items()}
    packet=supplied['source_packets'][str(number)]
    selection.rebuild_source_packet(packet)
    selection.validate_metadata({'proposals':[proposal]},{str(number):packet})
    if (candidate.get('number')!=number or candidate.get('candidate_id')!=briefs[number]['candidate_id']
        or candidate.get('status')!='HOLD_PEER_REVIEW' or proposal['decision']!='ACCEPT'
        or not any(p['verdict']=='REVIEW_REQUIRED' for p in peers.values())
        or candidate.get('proposal')!=proposal or candidate.get('peer_review')!=peers
        or candidate.get('discussion_sha256')!=discussion_sha256
        or candidate.get('selection_entry_hash')!=binding['entry_hashes'][str(number)]
        or candidate.get('source_packet_sha256')!=selection.preparation.digest(packet)
        or candidate.get('case_curation_eligible') is not False):
        raise ValueError('Exact original HOLD candidate/proposal/reviews required')
    issues=[{'issue_id':selection.preparation.digest({'role':v,'index':i,'issue':issue}),
             'role':v,'issue':deepcopy(issue)} for v in VOICES[:-1] for i,issue in enumerate(peers[v]['issues'])]
    gate=require_gate(offline_gate)
    context={'number':number,'candidate_id':candidate['candidate_id'],'candidate':candidate,
             'bundle':bundle,'supplied':supplied,'brief':briefs[number],'packet':packet,
             'proposal':proposal,'peers':peers,'issues':issues,'input_name':input_name,
             'discussion_name':name,'original_bindings':{'candidate':cp,'input':ip,'discussion':dp}}
    binding_hashes={k:v['sha256'] for k,v in context['original_bindings'].items()}
    binding_hashes.update(policy=selection.preparation.digest(POLICY),
        protocol=selection.preparation.digest({'system':REVISION_SYSTEM,'proposal':PROPOSAL_EXTRA,'peer':PEER_EXTRA,
                    'contracts':{s:selection.selection_contract(s,{'scope':'batch','entry_numbers':[number],'speaker':'sutrakar' if s=='proposal' else 'narada'}) for s in ('proposal','peer_review')}}),
        roles=selection.preparation.digest({'models':selection.MODELS,'providers':selection.PROVIDERS,'rates':selection.RATES}))
    context['binding']=binding_hashes
    return context,input_raw,{'gate_sha256':byte_hash(offline_gate),'gate':gate}


class RevisionCalls(selection.SelectionCalls):
    """Reuse fixed adapters/lock/timeout and existing lean model-view functions."""
    def voice(self,voice,payload):
        """Make one exact durable call; schema failures are never retried here."""
        stage=payload['stage']
        if (stage=='proposal' and voice!='sutrakar') or (stage=='peer_review' and voice not in VOICES[:-1]) or stage not in ('proposal','peer_review'):
            raise ValueError('Revision permits one Sutrakar proposal and three source peers only')
        view=selection.writing_view(payload)
        for brief in view['briefs']:brief.pop('selection_history',None)
        view['literal_formula_exclusions']=view.pop('forbidden_originals')
        history=view.pop('revision_history')
        view['prior_accepted_decisions']=[h for h in history if h['status']=='ACCEPTED_FOR_CASE_ASSIGNMENT']
        view['held_selection_decisions']=[h for h in history if h['status']=='HOLD_PEER_REVIEW']
        view['role_focus']=selection.ROLE_FOCUS[voice]
        instruction=selection.selection_contract(stage,payload)+(PROPOSAL_EXTRA if stage=='proposal' else PEER_EXTRA)
        slot=f"{payload['batch_id']}/{stage}"
        system=REVISION_SYSTEM+'\nROLE FOCUS: '+selection.ROLE_FOCUS[voice]
        envelope={'instruction':instruction,'input':view}
        selection.book.save_checkpoint(self.work/('request-'+stage+'-'+voice+'.json'),
            {'voice':voice,'stage':slot,'system':system,'payload':envelope,'max_output_tokens':POLICY['tokens'],
             'adapter_effort':POLICY['effort'] if selection.PROVIDERS[voice]=='anthropic' else 'UNCHANGED'})
        with self.lock:
            adapter=self.provider.adapters[voice];previous=getattr(adapter,'effort',None)
            if selection.PROVIDERS[voice]=='anthropic':adapter.effort=POLICY['effort']
            try:return call_with_lossless_framing(self.provider,voice,slot,system,envelope,POLICY['tokens'])
            except (ValueError,SourceFirstStopped):raise SourceFirstStopped('Revision transport/framing stopped; no automatic retry') from None
            finally:
                if selection.PROVIDERS[voice]=='anthropic':adapter.effort=previous


def _provider_proof(provider,voice,slot,answer):
    """Attest actual durable success/raw hashes; no fabricated request lineage."""
    key=provider_hash([voice,slot])
    with sqlite3.connect(provider.db_path) as db:
        row=db.execute('SELECT request_sha256,source_sha256,status,raw_sha256,result_sha256 FROM calls WHERE slot=?',(key,)).fetchone()
    if not row or row[2]!='SUCCESS' or row[1]!=provider_hash(provider.source_hashes) or row[4]!=provider_hash(answer) or byte_hash(provider.work_dir/'raw'/(key+'.txt'))!=row[3]:
        raise ValueError('Actual provider request/response proof missing or changed')
    return {'voice':voice,'stage':slot,'slot':key,'request_sha256':row[0],'source_sha256':row[1],
            'raw_response_sha256':row[3],'parsed_response_sha256':row[4],
            'model':selection.MODELS[voice][1],'provider':selection.PROVIDERS[voice]}


def _responses(answer,issues):
    """Validate exact per-old-issue audit coverage; return substantive response rows."""
    rows=answer.get('revision_responses')
    indexed=selection.preparation.indexed(rows,'issue_id','Revision responses')
    if set(indexed)!={i['issue_id'] for i in issues}:raise ValueError('Every original peer issue needs exactly one response')
    for row in rows:
        reason=row.get('reason_mr')
        if row.get('disposition') not in ('ADDRESSED','CONTESTED','CANDIDATE_REJECTED') or not isinstance(reason,str) or len(re.findall(r'[\u0900-\u097f]+',reason))<5:
            raise ValueError('Substantive Marathi issue response required')
    return rows


def _raw_copy(path,raw):
    """Save an exact original-byte copy only in the new root; replay never overwrites."""
    if path.exists():
        if path.read_bytes()!=raw:raise ValueError('Saved original-byte copy changed')
        return
    temporary=path.with_suffix(path.suffix+'.tmp');temporary.write_bytes(raw);temporary.replace(path)


def run(*,source_dir,number=1,candidate_sha256,input_sha256,discussion_sha256,offline_gate,work,
        live=False,resume=False,budget=4.,claude_cap=3.,max_calls=4,credentials_dir=None,registry=None):
    """Preflight by default; single-entry live opt-in or fake-only injected execution.

    Original artifacts remain immutable. Failure retains raw/reservations and
    permanently stops this root. Success replay verifies exact requests for free.
    """
    if type(live) is not bool or type(resume) is not bool or (live and registry is not None):raise ValueError('Explicit live/resume, offline injection only')
    if type(max_calls) is not int or max_calls!=4 or any(type(x) not in (int,float) or not math.isfinite(x) or x<=0 for x in (budget,claude_cap)):raise ValueError('Positive fixed caps and exactly four allowed calls required')
    context,input_raw,receipt=preflight(source_dir=source_dir,number=number,candidate_sha256=candidate_sha256,input_sha256=input_sha256,discussion_sha256=discussion_sha256,offline_gate=offline_gate)
    work=_work_path(Path(work))
    for name in (source_dir,offline_gate,ROOT/'scripts',ROOT/'tests',ROOT/'src'):
        path=Path(name).resolve()
        if path==work or path in work.parents or work in path.parents:raise ValueError('New revision root must be disjoint from originals/code/gate')
    manifest={'version':POLICY['version'],'binding':context['binding'],'live':live,'budget':budget,'claude_cap':claude_cap,'max_calls':max_calls}
    if resume:
        if load(work/'run-manifest.json')!=manifest:raise ValueError('Revision resume binding/cap changed')
        if (work/'terminal-stop.json').exists():raise SourceFirstStopped('Revision root is terminally stopped; no retry')
    elif work.exists():raise ValueError('Fresh short revision root required')
    if not live and registry is None:return {'status':'OFFLINE_PREFLIGHT_PASS','candidate_id':context['candidate_id'],'paid_calls':0,'binding':context['binding']}
    if live and credentials_dir is None:raise ValueError('Explicit credentials directory required')
    if not resume:
        work.mkdir(parents=True,exist_ok=False);save(work/'run-manifest.json',manifest)
    with _exclusive(work):
        # Preflight may race a completed/failed owner; authority is rechecked
        # under the same lock, before receipts, adapter construction or replay.
        if load(work/'run-manifest.json')!=manifest:
            raise ValueError('Revision manifest changed before lock acquisition')
        if (work/'terminal-stop.json').exists():
            raise SourceFirstStopped('Revision root is terminally stopped; no retry')
        receipts=work/'execution-receipts';receipts.mkdir(exist_ok=True)
        ordinal=max((int(p.stem) for p in receipts.glob('*.json') if p.stem.isdigit()),default=0)+1
        receipt_path=receipts/f'{ordinal:06d}.json';save(receipt_path,{**receipt,'binding':context['binding'],'paid_execution':live})
        options=dict(source_hashes=context['binding'],max_usd=budget,claude_cap_usd=claude_cap,max_calls=4,resume=resume)
        provider=(create_live_provider(work/'provider',credentials_dir=Path(credentials_dir),enable_live=True,**options) if live else SourceFirstProvider(work/'provider',registry,**options))
        calls=RevisionCalls(provider,work);before_calls=provider.dispatcher.calls
        report={'status':'RUNNING','candidate_id':context['candidate_id'],'number':number,'composition_calls':0,'validator_calls':0}
        try:
            namespace=f"saved-revision-v1/{context['candidate_id']}/{number}"
            binding=context['bundle']['discussion']['_batch']
            base={'number':0,'scope':'batch','batch_id':namespace,'entry_numbers':[number],
                'briefs':[deepcopy(context['brief'])],'sources':{str(number):context['packet']},
                'sources_by_entry':{str(number):context['packet']},'source_first_selection':SOURCE_FIRST_SELECTION,
                'prior_formulas':binding['prior_formulas'],'forbidden_originals':binding['forbidden_originals'],
                'used_case_ids':[],'discussion':deepcopy(context['bundle']['discussion']),
                'revision_history':context['supplied']['prior_accepted_decisions'],
                'original_proposal':context['proposal'],'original_peer_review':context['peers'],
                'original_peer_issues':context['issues'],'current_formula_shape':formula_shape(context['proposal'])}
            records=[]
            def stage(voice,kind,payload):
                """Call/verify one slot, preserving its first audit record on replay."""
                answer=calls.voice(voice,{**payload,'stage':kind,'speaker':voice})
                proof=_provider_proof(provider,voice,namespace+'/'+kind,answer)
                checkpoint=work/(kind+'-'+voice+'.json')
                saved={'answer':answer,'provider':proof}
                if checkpoint.exists():
                    previous=load(checkpoint)
                    if previous['answer']!=answer or {k:v for k,v in previous['provider'].items() if k not in ('first_validation_receipt','request_document')}!=proof:
                        raise ValueError('Revision stage checkpoint drift')
                    proof=previous['provider']
                    for reference in (proof['first_validation_receipt'],proof['request_document']):
                        if byte_hash(work/reference['path'])!=reference['sha256']:
                            raise ValueError('Historical execution/request proof drift')
                else:
                    proof['first_validation_receipt']={'path':str(receipt_path.relative_to(work)),'sha256':byte_hash(receipt_path)}
                    request_document=work/('request-'+kind+'-'+voice+'.json')
                    proof['request_document']={'path':request_document.name,'sha256':byte_hash(request_document)}
                    saved['provider']=proof;save(checkpoint,saved)
                records.append(proof)
                return answer
            answer=stage('sutrakar','proposal',base)
            _check_answer('proposal','sutrakar',answer,base)
            selection.validate_metadata(answer,base['sources_by_entry']);responses=_responses(answer,context['issues'])
            proposal=answer['proposals'][0]
            fresh={}
            for voice in VOICES[:-1]:
                peer_payload={**base,'proposal':{'proposals':[proposal]},'revision_responses':responses,'current_formula_shape':formula_shape(proposal)}
                fresh[voice]=stage(voice,'peer_review',peer_payload)
                _check_answer('peer_review',voice,fresh[voice],peer_payload)
            # Preserve exact inputs, maps/_batch and every unselected output.
            derived=deepcopy(context['bundle'])
            derived['proposal']['proposals']=[deepcopy(proposal) if p['number']==number else p for p in derived['proposal']['proposals']]
            for voice in VOICES[:-1]:
                new=fresh[voice]['reviews'][0]
                derived['peer_review'][voice]['reviews']=[deepcopy(new) if r['number']==number else r for r in derived['peer_review'][voice]['reviews']]
            accepted=proposal['decision']=='ACCEPT';peers={v:fresh[v]['reviews'][0] for v in VOICES[:-1]}
            disputed=any(p['verdict']!='PASS' for p in peers.values())
            status=('HOLD_PEER_REVIEW' if disputed else 'ACCEPTED_FOR_CASE_ASSIGNMENT') if accepted else 'REJECTED'
            for key,decision in (('accepted_numbers','ACCEPT'),('rejected_numbers','REJECT')):
                if key in derived:derived[key]=[p['number'] for p in derived['proposal']['proposals'] if p['decision']==decision]
            provenance={'version':POLICY['version'],'original_bindings':context['original_bindings'],
                'original_proposal':context['proposal'],'original_peer_review':context['peers'],
                'original_issues':context['issues'],'revision_responses':responses,'provider_calls':records,
                'revised_proposal_sha256':selection.preparation.digest(proposal),'fresh_peer_review_sha256':selection.preparation.digest(peers),
                'original_rounds_sha256':selection.preparation.digest(context['bundle']['discussion']),
                'original_feedback_still_targets_original_proposal':True,'fresh_feedback_targets_revised_proposal':True,
                'author_approval':'PENDING','publication_approved':False}
            selection.book.save_checkpoint(work/'revision-provenance.json',provenance)
            pointer={'path':'revision-provenance.json','sha256':byte_hash(work/'revision-provenance.json')}
            derived['revision_provenance']=pointer
            selection.book.save_checkpoint(work/context['discussion_name'],derived)
            _raw_copy(work/context['input_name'],input_raw)
            candidate={**deepcopy(context['candidate']),'proposal':proposal,'peer_review':peers,
                'discussion_sha256':byte_hash(work/context['discussion_name']),'status':status,
                'case_curation_eligible':accepted and not disputed,'composition_approved':False,'revision_provenance':pointer}
            selection.book.save_checkpoint(work/f'candidate-{number:03d}.json',candidate)
            for proof in context['original_bindings'].values():
                if byte_hash(proof['path'])!=proof['sha256']:raise ValueError('Original input changed during revision')
            result={'status':status,'candidate_id':context['candidate_id'],'number':number,
                'candidate':{'path':f'candidate-{number:03d}.json','sha256':byte_hash(work/f'candidate-{number:03d}.json')},
                'discussion':{'path':context['discussion_name'],'sha256':byte_hash(work/context['discussion_name'])},
                'input':{'path':context['input_name'],'sha256':byte_hash(work/context['input_name'])},'revision_provenance':pointer,
                'author_approval':'PENDING','publication_approved':False}
            selection.book.save_checkpoint(work/'result.json',result);report.update(result)
        except Exception as error:
            report.update(status='STOPPED',error_type=type(error).__name__)
            save(work/'terminal-stop.json',{'status':'STOPPED','binding':context['binding'],'error_type':type(error).__name__})
            raise SourceFirstStopped('Saved proposal revision stopped; inspect retained raw/checkpoints, no retry') from None
        finally:
            report.update(calls=provider.dispatcher.calls,new_calls=provider.dispatcher.calls-before_calls,
                reservation_usd=provider.dispatcher.reserved_usd,claude_reservation_usd=provider.spend_guard.reserved_usd,
                actual_invoice_usd=None,reservation_is_not_actual_invoice=True)
            save(work/'report.json',report)
        return report


def main(argv=None):
    """Parse one-entry CLI; return sanitized status without exposing credentials."""
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('source-dir','candidate-sha256','input-sha256','discussion-sha256','offline-gate','work'):
        parser.add_argument('--'+name,required=True)
    parser.add_argument('--number',type=int,default=1)
    parser.add_argument('--live',action='store_true');parser.add_argument('--resume',action='store_true')
    parser.add_argument('--budget',type=float,default=4.);parser.add_argument('--claude-cap',type=float,default=3.)
    parser.add_argument('--max-calls',type=int,default=4);parser.add_argument('--credentials-dir')
    try:result=run(**vars(parser.parse_args(argv)))
    except Exception as error:
        print(json.dumps({'status':'STOPPED','error_type':type(error).__name__}));return 2
    print(json.dumps(result,ensure_ascii=False));return 0


if __name__=='__main__':
    raise SystemExit(main())
