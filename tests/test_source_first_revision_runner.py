"""Fake-only single-entry revision boundaries; no real model/credential access."""
from copy import deepcopy
import json
from pathlib import Path
import pytest

from scripts import run_source_first_revision as runner
from scripts import run_source_first_selection as selection
from src.orchestration.research_council import ResearchCouncil
from tests.test_source_first_selection_runner import options as selection_options, SelectionRegistry, approved_optional_packet


class OriginalHeldRegistry(SelectionRegistry):
    """Produce real source-run artifacts with one grounded synthetic old issue."""
    def respond(self,voice,payload):
        """Preserve all original rounds; mark matching old proposals for review."""
        result=super().respond(voice,payload)
        if payload['stage']=='peer_review' and voice=='researcher':
            for row in result['reviews']:
                row.update(verdict='REVIEW_REQUIRED',issues=[{'field':'derivation',
                    'quote':'Synthetic test derivation only','reason':'Clarify the actual supplementary relation',
                    'severity':'medium'}])
        return result


class RevisionRegistry(SelectionRegistry):
    """Return four explicit synthetic revision outputs using fixed fake models."""
    def __init__(self,hold=False,reject=False,missing_response=False,bad_quote=False):
        """Configure one-shot outcomes; never construct credentials or a real SDK."""
        super().__init__();self.hold=hold;self.reject=reject
        self.missing_response=missing_response;self.bad_quote=bad_quote

    def respond(self,voice,payload):
        """Read saved context and return current-target feedback, not old quotes."""
        stage=payload['stage'];assert stage in ('proposal','peer_review')
        assert set(payload['discussion'])=={'position','challenge','reply'}
        assert payload['original_peer_issues']
        result=super().respond(voice,payload)
        if stage=='proposal':
            if self.reject:
                result['proposals']=[{'number':payload['entry_numbers'][0],'decision':'REJECT',
                    'rejection_reason':'कृत्रिम चाचणीपुरता हा मर्यादित प्रस्ताव नाकारण्याचा स्पष्ट निर्णय आहे'}]
            else:
                p=result['proposals'][0]
                p['proposed_sutra']='सत्यं व्यवसायस्य मूलम्'
                p['derivation']='Revised supplementary relation for the existing structural fixture only'
                # Optional supplied references need not all be selected.
                p['selected_source_ids']=[i for i in p['selected_source_ids'] if not i.startswith('MRB-')]
            result['revision_responses']=[] if self.missing_response else [
                {'issue_id':i['issue_id'],'disposition':'CONTESTED',
                 'reason_mr':'कृत्रिम चाचणीत दिलेल्या स्रोतांनुसार संबंध आणि मर्यादा स्पष्ट केल्या आहेत'}
                for i in payload['original_peer_issues']]
        elif voice=='researcher' and (self.hold or self.bad_quote):
            p=payload['proposal']['proposals'][0]
            result['reviews'][0].update(verdict='REVIEW_REQUIRED',issues=[{
                'field':'derivation','quote':'Synthetic test derivation only' if self.bad_quote else p['derivation'],
                'reason':'Synthetic unresolved current scope objection','severity':'medium'}])
        return result


def revision_options(tmp_path,monkeypatch,number=1,original_target=None,with_optional=False):
    """Create an actual saved HOLD source run, current synthetic gate and new root.

    Return run kwargs. Integration tests may reuse this builder without source
    data edits; it never certifies real source meaning or business acceptance.
    """
    setup_root=tmp_path/'s';setup_root.mkdir()
    opts=selection_options.__wrapped__(setup_root,monkeypatch)
    if with_optional:
        builder=selection.build_selection
        def augmented(*args,**kwargs):
            """Attach an existing synthetic attested proof before original debate."""
            data=builder(*args,**kwargs)
            for entry in data['entries']:
                if entry['number']==number:entry['source_packet']=approved_optional_packet(entry['source_packet'])
            return data
        monkeypatch.setattr(selection,'build_selection',augmented)
    selection.run(**opts,target=original_target or number,registry=OriginalHeldRegistry())
    source=opts['work'];candidate=runner.load(source/f'candidate-{number:03d}.json')
    discussion=source/candidate['discussion_file'];supplied=source/candidate['discussion_file'].replace('-discussion.json','-input.json')
    monkeypatch.setattr(runner,'code_bindings',lambda:{'revision-fixture':'b'*64})
    gate=tmp_path/'gate.json'
    runner.save(gate,{'status':'PASS','paid_calls':0,'code_sha256':runner.code_bindings(),
        'tests':[{'path':p,'passed':1,'failed':0,'errors':0} for p in runner.REQUIRED_TESTS]})
    return dict(source_dir=source,number=number,candidate_sha256=runner.byte_hash(source/f'candidate-{number:03d}.json'),
        input_sha256=runner.byte_hash(supplied),discussion_sha256=runner.byte_hash(discussion),
        offline_gate=gate,work=tmp_path/'r',budget=4.,claude_cap=3.,max_calls=4)


@pytest.fixture(autouse=True)
def no_live(monkeypatch):
    """Fail any real registry/credential construction; every adapter must be fake."""
    def forbidden(*args,**kwargs):
        """Reject live access before any credential value can be read."""
        pytest.fail('No live providers or credentials in revision tests')
    monkeypatch.setattr(runner,'create_live_provider',forbidden)
    monkeypatch.setattr(selection,'create_live_provider',forbidden)
    monkeypatch.setattr('scripts.run_research_book.load_project_credentials',forbidden)
    monkeypatch.setattr('src.providers.registry.ProviderRegistry',forbidden)


@pytest.fixture
def options(tmp_path,monkeypatch):
    """Return one held original and isolated output; no real source assertions."""
    return revision_options(tmp_path,monkeypatch)


def snapshot(directory):
    """Return exact source-file hashes to detect any forbidden original mutation."""
    return {str(p.relative_to(directory)):runner.byte_hash(p) for p in directory.rglob('*') if p.is_file()}


def test_default_preflight_does_not_write_or_construct_provider(options):
    """Prekey validation is read-only until explicit live opt-in or fake injection."""
    result=runner.run(**options)
    assert result['status']=='OFFLINE_PREFLIGHT_PASS' and not options['work'].exists()


def test_four_calls_derived_views_proof_medium_effort_and_free_replay(options,monkeypatch):
    """Four new calls preserve all rounds/inputs and exactly replay without billing."""
    before=snapshot(options['source_dir']);fake=RevisionRegistry()
    def no_rounds(*args,**kwargs):
        """Trip if the wrapper tries to repeat completed source discussion."""
        pytest.fail('No repeated source discussion')
    monkeypatch.setattr(ResearchCouncil,'run_batch_discussion',no_rounds)
    result=runner.run(**options,registry=fake)
    assert result['status']=='ACCEPTED_FOR_CASE_ASSIGNMENT' and len(fake.calls)==4
    assert [c['voice'] for c in fake.calls]==['sutrakar','narada','shandilya','researcher']
    assert result['composition_calls']==result['validator_calls']==0
    for call in fake.calls:
        assert call['timeout']==240 and call['tokens']==4096
        if selection.PROVIDERS[call['voice']]=='anthropic':assert call['effort']=='medium'
    assert snapshot(options['source_dir'])==before
    old=runner.load(options['source_dir']/'selection-1-discussion.json')
    new=runner.load(options['work']/'selection-1-discussion.json')
    assert old['discussion']==new['discussion']
    assert (options['source_dir']/'selection-1-input.json').read_bytes()==(options['work']/'selection-1-input.json').read_bytes()
    candidate=runner.load(options['work']/'candidate-001.json')
    assert candidate['case_curation_eligible'] is True and candidate['composition_approved'] is False
    proof=runner.load(options['work']/'revision-provenance.json')
    assert proof['original_proposal']==old['proposal']['proposals'][0]
    assert proof['original_peer_review']['researcher']['verdict']=='REVIEW_REQUIRED'
    assert len(proof['provider_calls'])==4
    for row in proof['provider_calls']:
        assert all(len(row[k])==64 for k in ('request_sha256','raw_response_sha256','parsed_response_sha256'))
        assert runner.byte_hash(options['work']/row['request_document']['path'])==row['request_document']['sha256']
    recorded=(options['work']/'result.json').read_bytes()
    resumed=runner.run(**options,resume=True,registry=fake)
    assert len(fake.calls)==4 and resumed['new_calls']==0
    assert recorded==(options['work']/'result.json').read_bytes()


@pytest.mark.parametrize('mode,expected',[('hold','HOLD_PEER_REVIEW'),('reject','REJECTED')])
def test_hold_or_reject_saved_without_automatic_retry(options,mode,expected):
    """Fresh unanimous PASS remains mandatory; every outcome still uses four calls."""
    fake=RevisionRegistry(**{mode:True});result=runner.run(**options,registry=fake)
    assert result['status']==expected and len(fake.calls)==4
    candidate=runner.load(options['work']/'candidate-001.json')
    assert candidate['case_curation_eligible'] is False
    if mode=='reject':assert 'proposed_sutra' not in candidate['proposal']


def test_missing_old_issue_response_is_one_call_terminal_stop(options):
    """Incomplete reconciliation cannot trigger any automatic paid schema retry."""
    fake=RevisionRegistry(missing_response=True)
    with pytest.raises(runner.SourceFirstStopped):runner.run(**options,registry=fake)
    assert len(fake.calls)==1
    report=runner.load(options['work']/'report.json')
    assert report['reservation_usd']>0 and report['status']=='STOPPED'
    with pytest.raises(runner.SourceFirstStopped):runner.run(**options,resume=True,registry=fake)
    assert len(fake.calls)==1


def test_fresh_review_cannot_quote_abandoned_original_wording(options):
    """Old issue quotes remain old feedback; fresh issues target revised text."""
    fake=RevisionRegistry(bad_quote=True)
    with pytest.raises(runner.SourceFirstStopped):runner.run(**options,registry=fake)
    assert len(fake.calls)==4 and not (options['work']/'result.json').exists()


def test_subset_of_offered_verified_supplementary_refs_is_allowed(tmp_path,monkeypatch):
    """Optional offered support need not be selected; both sutras/support remain."""
    opts=revision_options(tmp_path,monkeypatch,with_optional=True)
    fake=RevisionRegistry();runner.run(**opts,registry=fake)
    candidate=runner.load(opts['work']/'candidate-001.json')
    assert len(candidate['proposal']['selected_source_ids'])==3
    assert all(not i.startswith('MRB-') for i in candidate['proposal']['selected_source_ids'])


def test_full_batch_unselected_outputs_are_untouched(tmp_path,monkeypatch):
    """Single-entry revision cannot alter siblings in the saved batch envelope."""
    opts=revision_options(tmp_path,monkeypatch,number=2,original_target=2)
    fake=RevisionRegistry();runner.run(**opts,registry=fake)
    candidate=runner.load(opts['work']/'candidate-002.json')
    name=candidate['discussion_file']
    old=runner.load(opts['source_dir']/name);new=runner.load(opts['work']/name)
    assert new['discussion']==old['discussion']
    assert [p for p in new['proposal']['proposals'] if p['number']!=2]==[p for p in old['proposal']['proposals'] if p['number']!=2]
    for v in runner.VOICES[:-1]:
        assert [r for r in new['peer_review'][v]['reviews'] if r['number']!=2]==[r for r in old['peer_review'][v]['reviews'] if r['number']!=2]


@pytest.mark.parametrize('artifact',['candidate','input','discussion','gate'])
def test_drift_or_stale_gate_stops_before_keys(options,artifact):
    """Any changed original/current-code gate fails before live factory access."""
    if artifact=='gate':
        value=runner.load(options['offline_gate']);value['code_sha256']={};runner.save(options['offline_gate'],value)
    else:options[artifact+'_sha256']='0'*64
    with pytest.raises(ValueError):runner.run(**options,live=True,credentials_dir='never-load')


def test_execution_gate_receipt_change_does_not_invalidate_paid_cache(options):
    """Current exact gate stays mandatory, outside immutable request/source identity."""
    fake=RevisionRegistry();runner.run(**options,registry=fake)
    manifest=(options['work']/'run-manifest.json').read_bytes()
    gate=runner.load(options['offline_gate']);gate['tests'][0]['passed']=2;runner.save(options['offline_gate'],gate)
    runner.run(**options,resume=True,registry=fake)
    assert len(fake.calls)==4 and manifest==(options['work']/'run-manifest.json').read_bytes()
    assert len(list((options['work']/'execution-receipts').glob('*.json')))==2


def test_mechanical_counts_are_not_relabelled_as_grammar_approval():
    """Reported five-word objection cannot override the exact three-word count."""
    shape=runner.formula_shape({'proposed_sutra':'मूल्यपरीक्षा लाभात् पूर्वम्'})
    assert shape['words']==3 and shape['unicode_characters']==27
    assert shape['grammar_certified'] is False


def test_resume_cap_change_rejected_without_additional_calls(options):
    """A fresh namespace never silently changes its reservation caps."""
    fake=RevisionRegistry();runner.run(**options,registry=fake)
    with pytest.raises(ValueError):runner.run(**{**options,'budget':5.},resume=True,registry=fake)
    assert len(fake.calls)==4



@pytest.mark.parametrize('race',['terminal','manifest'])
def test_lock_rechecks_terminal_and_manifest_before_receipt_or_provider(options,monkeypatch,race):
    """A marker/manifest change after preflight must stop even a free cached replay."""
    from contextlib import contextmanager
    fake=RevisionRegistry();runner.run(**options,registry=fake)
    before_receipts=list((options['work']/'execution-receipts').glob('*.json'))
    before_result=(options['work']/'result.json').read_bytes()
    real_lock=runner._exclusive
    @contextmanager
    def changed_under_lock(path):
        """Inject the reviewed race exactly between outer checks and lock yield."""
        with real_lock(path):
            if race=='terminal':runner.save(path/'terminal-stop.json',{'status':'STOPPED','test':'late owner'})
            else:
                manifest=runner.load(path/'run-manifest.json');manifest['budget']+=1
                runner.save(path/'run-manifest.json',manifest)
            yield
    def forbidden_provider(*args,**kwargs):
        """Ensure locked checks precede even fake provider construction."""
        pytest.fail('Provider constructed despite late terminal/manifest state')
    monkeypatch.setattr(runner,'_exclusive',changed_under_lock)
    monkeypatch.setattr(runner,'SourceFirstProvider',forbidden_provider)
    with pytest.raises((runner.SourceFirstStopped,ValueError)):
        runner.run(**options,resume=True,registry=fake)
    assert len(fake.calls)==4
    assert list((options['work']/'execution-receipts').glob('*.json'))==before_receipts
    assert (options['work']/'result.json').read_bytes()==before_result
