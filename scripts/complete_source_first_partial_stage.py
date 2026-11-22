"""Prepare/complete/apply one exact Narada partial-stage completion.

No call by default. prepare is offline; complete requires --live and a current
external exact-code gate; apply is a separate offline explicit action. Completion
is one Gemini request for missing rows only, with its own <=0.25USD cap. Original
source cap/reservation/raw/dispatch audit are never reset or imported twice.
"""
from pathlib import Path
import argparse,hashlib,json,math,sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from scripts import run_source_first_selection as s
from src.orchestration import source_first_partial_completion as partial
from src.orchestration.source_first_provider import SourceFirstProvider,create_live_provider,call_with_lossless_framing,_exclusive,_work_path,SourceFirstStopped

REQUIRED_TESTS=('tests/test_source_first_partial_completion.py','tests/test_source_first_partial_completion_runner.py',
 'tests/test_source_first_provider.py','tests/test_source_first_selection_runner.py','tests/test_research_council.py',
 'tests/test_providers.py','tests/test_dispatch.py')


def code_bindings():
    """Seal current code and required tests; return exact byte hashes without keys."""
    paths={p for d in ('src','scripts') for p in (ROOT/d).rglob('*.py')}|{ROOT/n for n in REQUIRED_TESTS}
    return {p.relative_to(ROOT).as_posix():s.byte_hash(p) for p in sorted(paths)}


def require_gate(path):
    """Reject stale/missing offline proofs before provider or adoption authority."""
    gate=s.load(path);rows=gate.get('tests',[])
    if gate.get('status')!='PASS' or gate.get('paid_calls')!=0 or gate.get('code_sha256')!=code_bindings():raise ValueError('Current completion code/test gate required')
    for name in REQUIRED_TESTS:
        found=[r for r in rows if r.get('path')==name]
        if len(found)!=1 or type(found[0].get('passed')) is not int or found[0]['passed']<1 or found[0].get('failed')!=0 or found[0].get('errors')!=0:raise ValueError('Completion regression not passed')
    return gate


def complete(*,plan_path,plan_sha256,work,offline_gate,live=False,resume=False,credentials_dir=None,budget=.25,registry=None):
    """One explicit missing-row call, or preflight only; never auto-apply authority.

    Fake registry injection is offline. Failures retain reservation/raw and stop
    the namespace; successful resume verifies exact cached identity with no SDK.
    """
    if s.byte_hash(plan_path)!=plan_sha256:raise ValueError('Frozen completion plan changed')
    plan=s.load(plan_path);partial._verify_original(plan);gate=require_gate(offline_gate)
    if type(live) is not bool or type(resume) is not bool or live and registry is not None:raise ValueError('Explicit live/resume; fake injection offline only')
    if type(budget) not in (int,float) or not math.isfinite(budget) or not 0<budget<=.25:raise ValueError('Explicit separate <=0.25USD allowance required')
    work=_work_path(Path(work));source=Path(plan['provider_work']).parent.resolve()
    for item in (source,Path(plan_path).resolve(),Path(offline_gate).resolve(),ROOT/'src',ROOT/'scripts',ROOT/'tests'):
        if work==item or work in item.parents or item in work.parents:raise ValueError('Fresh completion work must be disjoint from original proof/code')
    manifest={'kind':'MISSING_PEER_COMPLETION','plan_sha256':plan_sha256,'budget':budget,'live':live,'max_calls':1}
    if resume:
        if s.load(work/'run-manifest.json')!=manifest:raise ValueError('Completion resume binding changed')
    elif work.exists():raise ValueError('Fresh short completion root required')
    if not live and registry is None:return {'status':'OFFLINE_PREFLIGHT_PASS','missing_numbers':plan['missing_numbers'],'paid_calls':0}
    if live and credentials_dir is None:raise ValueError('Explicit credential directory required')
    if not resume:work.mkdir(parents=True);s.save(work/'run-manifest.json',manifest)
    with _exclusive(work):
        if s.load(work/'run-manifest.json')!=manifest or (work/'terminal-stop.json').exists():raise SourceFirstStopped('Completion locked state forbids continuation')
        receipts=work/'execution-receipts';receipts.mkdir(exist_ok=True)
        index=len(list(receipts.glob('*.json')))+1;s.save(receipts/f'{index:06d}.json',{'gate':gate,'gate_sha256':s.byte_hash(offline_gate),'manifest':manifest})
        options=dict(source_hashes={'partial_plan':partial.digest(plan)},max_usd=budget,max_calls=1,claude_cap_usd=.001,resume=resume)
        provider=create_live_provider(work/'provider',credentials_dir=Path(credentials_dir),enable_live=True,**options) if live else SourceFirstProvider(work/'provider',registry,**options)
        report={'status':'RUNNING','original_reservation_reset':False}
        try:
            call=partial.completion_call(plan);adapter=provider.adapters['narada'];adapter.timeout_seconds=240
            s.book.save_checkpoint(work/'actual-request.json',call)
            answer=call_with_lossless_framing(provider,call['voice'],call['stage'],call['system'],call['payload'],call['max_output_tokens'],generation_options=call['generation_options'])
            receipt=partial.finalize_receipt(plan,provider.work_dir,completion_budget=budget)
            s.book.save_checkpoint(work/'partial-stage-completion.json',receipt)
            report.update(status='COMPLETE_PENDING_EXPLICIT_APPLY',numbers=[r['number'] for r in answer['reviews']],receipt=str(work/'partial-stage-completion.json'))
        except Exception as error:
            s.save(work/'terminal-stop.json',{'error_type':type(error).__name__});raise SourceFirstStopped('Completion stopped; no automatic retry') from None
        finally:
            report.update(calls=provider.dispatcher.calls,reservation_usd=provider.dispatcher.reserved_usd,actual_invoice_usd=None)
            s.save(work/'report.json',report)
        return report


def main(argv=None):
    """Dispatch explicit offline prepare/apply or opt-in complete; never auto-chain."""
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='action',required=True)
    prepare=sub.add_parser('prepare')
    for name in ('provider-work','council-db','source-input','forbidden-from-discussion','failed-slot','request-sha256','raw-sha256','source-sha256','output'):prepare.add_argument('--'+name,required=True)
    run=sub.add_parser('complete')
    for name in ('plan-path','plan-sha256','work','offline-gate'):run.add_argument('--'+name,required=True)
    run.add_argument('--live',action='store_true');run.add_argument('--resume',action='store_true');run.add_argument('--credentials-dir');run.add_argument('--budget',type=float,default=.25)
    apply=sub.add_parser('apply')
    for name in ('receipt','receipt-sha256','offline-gate'):apply.add_argument('--'+name,required=True)
    args=vars(parser.parse_args(argv));action=args.pop('action')
    if action=='complete':result=complete(**args)
    elif action=='apply':
        require_gate(args['offline_gate'])
        if s.byte_hash(args['receipt'])!=args['receipt_sha256']:raise ValueError('Explicit completion receipt hash changed')
        result=partial.apply_receipt(args['receipt'])
    else:
        forbidden=s.load(args['forbidden_from_discussion'])['discussion']['_batch']['forbidden_originals']
        result=partial.prepare_plan(args['provider_work'],args['council_db'],args['source_input'],forbidden,args['failed_slot'],expected_request_sha256=args['request_sha256'],expected_raw_sha256=args['raw_sha256'],expected_source_sha256=args['source_sha256'])
        with Path(args['output']).open('x',encoding='utf-8',newline='\n') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
        result={'status':'PLAN_ONLY_NO_AUTHORITY','output':args['output'],'missing_numbers':result['missing_numbers']}
    print(json.dumps(result,ensure_ascii=False));return 0


if __name__=='__main__':raise SystemExit(main())
