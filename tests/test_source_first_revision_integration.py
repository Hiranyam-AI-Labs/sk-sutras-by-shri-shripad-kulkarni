"""One offline HOLD-revision-to-composition integration with synthetic evidence.

Real boundary, capsule and selected-book validators remain unchanged. Fake
adapters certify orchestration only, never Sanskrit quality or historical truth.
"""
from copy import deepcopy
from pathlib import Path
import json

import pytest

from scripts import run_source_first_revision as revision
from scripts import run_source_first_selected_book as selected
from tests.test_source_first_book_runner import Registry
from tests.test_source_first_case_capsule import build_case_capsule, case_work
from tests.test_source_first_selected_book_runner import (
    CompositionRegistry, SelectedProposalRegistry, build_setup, receipt, repin, write,
)


def test_held_revision_fresh_reviews_feed_unchanged_capsule_and_selected_book(tmp_path, monkeypatch):
    """Reuse all old rounds, pay four fake revision slots, then validate and compose."""
    def no_live(*args, **kwargs):
        """Fail before any real credential loader or SDK registry can be used."""
        pytest.fail('Live credentials/providers forbidden in revision integration')

    monkeypatch.setattr(revision, 'create_live_provider', no_live)
    monkeypatch.setattr(selected, 'create_live_provider', no_live)
    monkeypatch.setattr('scripts.run_research_book.load_project_credentials', no_live)
    monkeypatch.setattr('src.providers.registry.ProviderRegistry', no_live)

    class HeldOriginal(SelectedProposalRegistry):
        """Produce a genuinely saved ACCEPT with one old substantive peer hold."""

        def respond(self, voice, payload):
            """Keep the source fixture unchanged except the selected original peer issue."""
            answer = super().respond(voice, payload)
            if payload['stage'] == 'peer_review' and voice == 'narada':
                for row in answer['reviews']:
                    if row['number'] == 1:
                        row.update(verdict='REVIEW_REQUIRED', issues=[{
                            'field': 'business_action_mr', 'quote': 'चाचणी कृती',
                            'reason': 'कृत्रिम चाचणीत कृतीची अट आणि मर्यादा स्पष्ट करणे आवश्यक',
                            'severity': 'major'}])
            return answer

    original_registry = HeldOriginal()
    setup = build_setup(tmp_path, monkeypatch, numbers=(2,), selection_registry=original_registry)
    source = Path(setup['tasks'][0]['candidate_record']['path']).parent
    original_candidate_path = source / 'candidate-001.json'
    original_candidate = selected.book.load(original_candidate_path)
    original_discussion_path = source / original_candidate['discussion_file']
    original_input_path = source / original_candidate['discussion_file'].replace('-discussion.json', '-input.json')
    originals = {p: p.read_bytes() for p in (original_candidate_path, original_input_path, original_discussion_path)}
    original_bundle = selected.book.load(original_discussion_path)
    assert original_candidate['status'] == 'HOLD_PEER_REVIEW'
    assert original_candidate['proposal']['decision'] == 'ACCEPT'
    assert original_candidate['peer_review']['narada']['verdict'] == 'REVIEW_REQUIRED'
    original_calls = len(original_registry.calls)

    class FreshRevision(Registry):
        """Allow only one revised proposal and the three fresh source-peer decisions."""

        def respond(self, voice, payload):
            """Respond to the exact old issue and review only the new current proposal."""
            assert payload['entry_numbers'] == [1]
            assert payload['stage'] in ('proposal', 'peer_review')
            assert payload['original_proposal'] == original_candidate['proposal']
            for stage in ('position', 'challenge', 'reply'):
                assert payload['discussion'][stage] == original_bundle['discussion'][stage]
            if payload['stage'] == 'proposal':
                assert voice == 'sutrakar'
                proposal = deepcopy(payload['original_proposal'])
                proposal.update(proposed_sutra='प्रमाणेन निर्णयः',
                    business_action_mr='चाचणी कृती ठराविक परिस्थितीत प्रत्यक्ष करून पाहणे सुधारित मर्यादा')
                self.revised = proposal
                return {'proposals': [proposal], 'revision_responses': [
                    {'issue_id': row['issue_id'], 'disposition': 'ADDRESSED',
                     'reason_mr': 'मूळ आक्षेपानुसार कृतीतील अट आणि मर्यादा स्पष्ट केल्या'}
                    for row in payload['original_peer_issues']]}
            assert voice in revision.VOICES[:-1]
            assert payload['proposal'] == {'proposals': [self.revised]}
            assert payload['revision_responses']
            return {'reviews': [{'number': 1, 'verdict': 'PASS', 'issues': []}]}

    gate = tmp_path / 'revision-gate.json'
    write(gate, {'status': 'PASS', 'paid_calls': 0, 'code_sha256': revision.code_bindings(),
        'tests': [{'path': p, 'passed': 1, 'failed': 0, 'errors': 0} for p in revision.REQUIRED_TESTS]})
    work = tmp_path / 'revision'
    options = dict(source_dir=source, number=1,
        candidate_sha256=selected.book.byte_hash(original_candidate_path),
        input_sha256=selected.book.byte_hash(original_input_path),
        discussion_sha256=selected.book.byte_hash(original_discussion_path), offline_gate=gate, work=work)
    fake = FreshRevision()
    report = revision.run(**options, registry=fake)
    assert report['status'] == 'ACCEPTED_FOR_CASE_ASSIGNMENT' and report['new_calls'] == 4
    assert [call['voice'] for call in fake.calls] == ['sutrakar', *revision.VOICES[:-1]]
    assert [json.loads(call['prompt'])['input']['stage'] for call in fake.calls] == [
        'proposal', 'peer_review', 'peer_review', 'peer_review']
    assert len(original_registry.calls) == original_calls

    paths = {name: work / report[name]['path'] for name in ('candidate', 'input', 'discussion', 'revision_provenance')}
    for name, path in paths.items():
        assert selected.book.byte_hash(path) == report[name]['sha256']
    candidate, bundle, supplied, provenance = [selected.book.load(paths[k])
        for k in ('candidate', 'discussion', 'input', 'revision_provenance')]
    assert paths['input'].read_bytes() == originals[original_input_path]
    assert bundle['discussion'] == original_bundle['discussion']
    assert candidate['proposal'] == fake.revised != original_candidate['proposal']
    assert set(candidate['peer_review']) == set(revision.VOICES[:-1])
    assert all(row['verdict'] == 'PASS' and not row['issues'] for row in candidate['peer_review'].values())
    digest = selected.book.preparation.digest
    assert provenance['fresh_peer_review_sha256'] == digest(candidate['peer_review'])
    assert provenance['revised_proposal_sha256'] == digest(candidate['proposal'])
    assert provenance['original_rounds_sha256'] == digest(original_bundle['discussion'])
    assert provenance['original_peer_review'] == original_candidate['peer_review']
    assert len(provenance['provider_calls']) == 4
    for proof in provenance['provider_calls']:
        checkpoint = selected.book.load(work / (proof['stage'].rsplit('/', 1)[1] + '-' + proof['voice'] + '.json'))
        assert checkpoint['provider'] == proof
        assert proof['parsed_response_sha256'] == revision.provider_hash(checkpoint['answer'])
        assert selected.book.byte_hash(work / 'provider' / 'raw' / (proof['slot'] + '.txt')) == proof['raw_response_sha256']
        assert selected.book.byte_hash(work / proof['request_document']['path']) == proof['request_document']['sha256']

    frozen_derived = {p: p.read_bytes() for p in [*paths.values(), work / 'result.json']}
    resumed = revision.run(**options, registry=fake, resume=True)
    assert resumed['status'] == report['status'] and resumed['new_calls'] == 0
    assert len(fake.calls) == 4
    assert all(p.read_bytes() == raw for p, raw in frozen_derived.items())
    assert all(p.read_bytes() == raw for p, raw in originals.items())

    brief = next(b for b in supplied['briefs'] if b['number'] == 1)
    sources = supplied['source_packets']['1']
    capsule = build_case_capsule(number=1, brief=brief, sources=sources,
        discussion=bundle['discussion'], proposal=bundle['proposal'], peer_review=bundle['peer_review'],
        case_work_dir=case_work(tmp_path / 'revision-case-proofs'), used_case_ids=set(), used_identity_keys=set(),
        case_slots=[{'kind': kind, 'case_id': ident,
            'fit_reason_mr': 'कृत्रिम चाचणीतील स्पष्ट मर्यादित उपयोग',
            'limitations_mr': 'ही ऐतिहासिक सत्यता प्रमाणित करणारी चाचणी नाही'}
            for kind, ident in (('positive', 'positive-a'), ('caution', 'caution-b'))])
    task = {'number': 1, 'brief': brief, 'source_packet': sources, 'case_capsule': capsule,
        **{key: {'path': str(paths[name]), 'sha256': report[name]['sha256']}
           for key, name in (('selection_input', 'input'), ('selection_discussion', 'discussion'), ('candidate_record', 'candidate'))}}
    validated = selected.validate_task(task, tmp_path, set(), set())
    assert validated['proposal'] == fake.revised and 'chapter' not in task['brief']
    setup['tasks'] = [task]; repin(setup); receipt(setup['options']['offline_gate'])
    writer = CompositionRegistry()
    composed = selected.run(**setup['options'], registry=writer)
    assert composed['status'] == 'READY_FOR_AUTHOR_REVIEW'
    assert composed['ready'][0]['draft']['new_sutra'] == fake.revised['proposed_sutra']
    assert [call['voice'] for call in writer.calls] == ['sutrakar', 'validator']
    assert selected.run(**setup['options'], registry=writer, resume=True) == composed
    assert len(writer.calls) == 2 and len(fake.calls) == 4
    assert all(p.read_bytes() == raw for p, raw in originals.items())
    assert composed['publication_approved'] is False and composed['author_approval'] == 'PENDING'
