"""Offline-only exact existing-span prepare/verify/apply; no provider or retry CLI.

prepare writes a NEW receipt after exact design GO. apply requires explicit
receipt SHA and current external offline tests under the existing source lock.
It does not materialize candidates or resume any source/model call. Parent owns
cached target81 replay; bulk source beyond81 stays paused.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from src.orchestration import source_first_evidence_anchor as anchor
from src.orchestration.source_first_provider import _exclusive
from scripts import run_source_first_selection as selection

REQUIRED_TESTS=('tests/test_source_first_evidence_anchor.py','tests/test_research_council.py','tests/test_source_first_selection_runner.py')


def code_bindings():
    """Return current source/script and required-test hashes, without keys or calls."""
    paths={p for d in ('src','scripts') for p in (ROOT/d).rglob('*.py')}|{ROOT/n for n in REQUIRED_TESTS}
    return {p.relative_to(ROOT).as_posix():anchor.byte_hash(p) for p in sorted(paths)}


def require_gate(path):
    """Require parent-sealed current tests before adoption; stale/malformed proofs stop."""
    gate=selection.load(path)
    if gate.get('status')!='PASS' or type(gate.get('paid_calls')) is not int or gate['paid_calls']!=0 or gate.get('code_sha256')!=code_bindings():raise ValueError('Current exact anchor execution gate required')
    for name in REQUIRED_TESTS:
        rows=[r for r in gate.get('tests',[]) if isinstance(r,dict) and r.get('path')==name]
        if len(rows)!=1 or type(rows[0].get('passed')) is not int or rows[0]['passed']<1 or any(type(rows[0].get(k)) is not int or rows[0][k]!=0 for k in ('failed','errors')):raise ValueError('Required anchor regression not passed')
    return gate


def prepare(*,design,design_sha256,approval,approval_sha256,output):
    """Write a fresh verified receipt only; original proof/cache files never change."""
    receipt=anchor.prepare_receipt(design,design_sha256,approval,approval_sha256)
    path=Path(output).resolve();source=Path(receipt['source_dir'])
    for protected in (source,ROOT/'src',ROOT/'scripts',ROOT/'tests',Path(design).resolve(),Path(approval).resolve()):
        if path==protected or protected in path.parents:raise ValueError('Fresh receipt must be outside original proofs/code')
    if path.exists():raise ValueError('Fresh receipt output required')
    path.parent.mkdir(parents=True,exist_ok=True)
    raw=json.dumps(receipt,ensure_ascii=False,indent=2)+'\n'
    # Exclusive creation preserves every earlier receipt; no replace/repair path.
    with path.open('x',encoding='utf-8',newline='\n') as stream:stream.write(raw)
    return {'status':'PREPARED_NOT_APPLIED','path':str(path),'sha256':anchor.byte_hash(path),'paid_calls':0}


def apply(*,receipt,receipt_sha256,offline_gate):
    """Explicit locked offline adoption with append-only per-invocation code audit.

    Rechecks gate and all proofs after lock acquisition. No SDK/key path exists;
    stale gate, conflicts and receipt drift propagate without retries or resets.
    """
    proof,_=anchor.verify_receipt(receipt,receipt_sha256);require_gate(offline_gate)
    source=Path(proof['source_dir']);path=Path(receipt).resolve()
    if source==path.parent or source in path.parents:raise ValueError('Receipt/audit directory must be outside original source run')
    with _exclusive(source):
        gate=require_gate(offline_gate);anchor.verify_receipt(receipt,receipt_sha256)
        audit=path.parent/'execution-receipts';audit.mkdir(exist_ok=True)
        ordinal=max((int(p.stem) for p in audit.glob('*.json') if p.stem.isdigit()),default=0)+1
        with (audit/f'{ordinal:06d}.json').open('x',encoding='utf-8',newline='\n') as stream:
            json.dump({'timestamp_utc':datetime.now(timezone.utc).isoformat(),'receipt_sha256':receipt_sha256,'gate_sha256':anchor.byte_hash(offline_gate),'gate':gate,'paid_calls':0},stream,ensure_ascii=False,indent=2);stream.write('\n')
        return anchor._adopt_locked(receipt,receipt_sha256)


def main(argv=None):
    """Dispatch explicit offline prepare, verify or apply; never resume a source run."""
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='action',required=True)
    prep=sub.add_parser('prepare')
    for name in ('design','design-sha256','approval','approval-sha256','output'):prep.add_argument('--'+name,required=True)
    for action in ('verify','apply'):
        command=sub.add_parser(action)
        for name in ('receipt','receipt-sha256'):command.add_argument('--'+name,required=True)
        if action=='apply':command.add_argument('--offline-gate',required=True)
    args=vars(parser.parse_args(argv));action=args.pop('action')
    if action=='prepare':result=prepare(**args)
    elif action=='apply':result=apply(**args)
    else:
        anchor.verify_receipt(args['receipt'],args['receipt_sha256']);result={'status':'VERIFIED_NO_APPLY','paid_calls':0}
    print(json.dumps(result,ensure_ascii=False));return 0


if __name__=='__main__':raise SystemExit(main())
