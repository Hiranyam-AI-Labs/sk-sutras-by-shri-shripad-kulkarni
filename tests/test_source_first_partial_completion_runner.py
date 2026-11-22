"""Fake-only operational completion checks; original source work is never edited."""
from pathlib import Path
import pytest
from scripts import complete_source_first_partial_stage as operator
from scripts import run_source_first_selection as s
from tests.test_source_first_partial_completion import setup_original,CompletionRegistry


@pytest.fixture
def options(tmp_path,monkeypatch):
    """Build actual fake terminal stage and an externally declared test gate."""
    plan,old,_,_=setup_original(tmp_path)
    path=tmp_path/'plan.json';s.save(path,plan)
    monkeypatch.setattr(operator,'code_bindings',lambda:{'fixture':'a'*64})
    gate=tmp_path/'gate.json';s.save(gate,{'status':'PASS','paid_calls':0,'code_sha256':operator.code_bindings(),
      'tests':[{'path':p,'passed':1,'failed':0,'errors':0} for p in operator.REQUIRED_TESTS]})
    def no_live(*args,**kwargs):
        """Trip on any credential or live registry construction."""
        pytest.fail('No real SDK/keys')
    monkeypatch.setattr(operator,'create_live_provider',no_live)
    return {'plan_path':path,'plan_sha256':s.byte_hash(path),'offline_gate':gate,'work':tmp_path/'new'},old


def test_preflight_and_one_call_complete_resume_never_apply_original(options):
    """The separate completion is cheap and reusable; adoption needs explicit action."""
    opts,old=options
    assert operator.complete(**opts)['status']=='OFFLINE_PREFLIGHT_PASS'
    assert not opts['work'].exists()
    registry=CompletionRegistry();result=operator.complete(**opts,registry=registry)
    assert result['status']=='COMPLETE_PENDING_EXPLICIT_APPLY' and result['calls']==1
    assert len(registry.calls)==1 and result['reservation_usd']<=.25
    assert operator.complete(**opts,resume=True,registry=registry)['calls']==1
    assert len(registry.calls)==1
    with __import__('sqlite3').connect(old.db_path) as db:
        assert db.execute("SELECT count(*) FROM calls WHERE status='HARD_FAILED'").fetchone()[0]==1


def test_over_cap_or_stale_gate_stops_before_keys(options):
    """No extra allowance or stale code can load the live completion factory."""
    opts,_=options
    with pytest.raises(ValueError):operator.complete(**opts,budget=.251,live=True,credentials_dir='never')
    gate=s.load(opts['offline_gate']);gate['code_sha256']={};s.save(opts['offline_gate'],gate)
    with pytest.raises(ValueError):operator.complete(**opts,live=True,credentials_dir='never')
