"""Prepare source-first research packets; live calls require explicit --live.

No business sutras or manuscripts are generated here. Paid screening uses the
unchanged researcher, followed by the unchanged independent fifth validator.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

from src.orchestration.source_first_provider import create_live_provider, call_with_lossless_framing
from src.orchestration.source_first_stage import digest, save_bound, screen_batch
from src.orchestration.source_first_research import prepare_research_batch

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'logs/source-first-generation-20261120'


# Load JSON and exact byte hash from one snapshot. Returns (value, digest);
# missing/invalid input raises before credentials or provider construction.
def load(path):
    data = Path(path).read_bytes()
    return json.loads(data), hashlib.sha256(data).hexdigest()


# Recompute the candidate release from original frozen evidence and compare it
# with saved bytes. Returns the primary manifest; drift raises before live setup.
def verified_manifest(work):
    spec = importlib.util.spec_from_file_location('candidate_preparer', work / 'prepare_candidate_manifest.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    expected = module.prepare()
    for name, data in expected.items():
        if (work / name).read_bytes() != data:
            raise ValueError('Candidate release differs from current frozen evidence')
    return json.loads(expected['candidate-manifest.json'])


# Normalize exact reviewed pair records, preserving devotional meanings/notes.
# Returns primary candidates plus whole-source hashes. Unknown eligibility or
# inconsistent source snapshots raises; no scores or meanings are invented.
def primary_inputs(manifest):
    if (manifest['manifest_role'] != 'PRIMARY_ONLY' or manifest['candidate_count'] != 243
            or len(manifest['candidates']) != manifest['candidate_count']):
        raise ValueError('Expected the accepted 243-primary release')
    rows, source_hashes = [], None
    for row in manifest['candidates']:
        current = {name: row['sources'][name]['file_sha256'] for name in ('narada', 'shandilya')}
        if source_hashes is not None and current != source_hashes:
            raise ValueError('Mixed working-source snapshots')
        source_hashes = current
        assessment = row['assessment']
        rows.append({'id': row['pair_id'],
                     'narada': row['sources']['narada']['record'],
                     'shandilya': row['sources']['shandilya']['record'],
                     'source_hashes': current, 'scores': assessment['scores'],
                     'total': assessment['total'], 'blockers': assessment['blockers'],
                     'failed_primary_minima': row['failed_primary_component_minima']})
    rows.sort(key=lambda row: (-row['total'], row['narada']['id'], row['shandilya']['id']))
    return rows, dict(source_hashes)


# Select only publicly attested, research-eligible supplementary corpus records.
# Returns normalized library plus all exact input hashes. The overlay may bind
# an earlier corpus snapshot, but each retained quote/locator must match exactly;
# historical whole-file provenance is preserved instead of silently relabelled.
def verified_library(work):
    corpus, corpus_hash = load(work / 'evidence-corpus.json')
    audit, audit_hash = load(work / 'evidence-corpus-independent-review.json')
    verification, verification_hash = load(work / 'evidence-primary-verification.json')
    if audit.get('gate') != 'PASS_WITH_LIMITS' or audit['reviewed_corpus']['sha256'] != corpus_hash:
        raise ValueError('Current corpus lacks exact independent review')
    records = {row['id']: row for row in corpus['passages']}
    checks = {row['record_id']: row for row in verification['records']}
    library = []
    for identifier in verification['eligible_calibration_record_ids']:
        record, checked = records[identifier], checks[identifier]
        if (record['reuse_status'] != 'QUALIFIED_RESEARCH_READY' or record['blockers']
                or checked['status'] != 'MATCH' or not checked['eligible_for_small_calibration']
                or checked['narada_shandilya_repeat']
                or record['original_passage'] != checked['existing_quote']
                or record['locator'] != checked['existing_locator']
                or record['passage_sha256'] != checked['existing_passage_sha256']):
            raise ValueError('Supplementary quotation verification or eligibility drift')
        library.append({'source_id': identifier, 'source_sha256': corpus_hash,
                        'location': record['locator'], 'canonical_passage': record['original_passage'],
                        'passage_sha256': record['passage_sha256'], 'title': record['work'],
                        'meaning_mr': record['faithful_meaning_mr'],
                        'context_mr': record['meaning_qualifications_mr'],
                        'eligible': True, 'verified': True,
                        'verification_record': checked, 'source_record': record})
    if not library:
        raise ValueError('No independently attested supplementary library available')
    return library, {'evidence_corpus': corpus_hash, 'corpus_review': audit_hash,
                     'primary_verification': verification_hash}


# Attach pair-specific selection IDs without changing the shared canonical text.
# Returns plain evidence rows consumed by the offline gate; oversize batches
# raise there rather than silently truncating the evidence menu.
def pair_evidence(candidates, library):
    return [{**reference, 'id': f"{candidate['id']}::{reference['source_id']}",
             'candidate_id': candidate['id']}
            for candidate in candidates for reference in library]


# Bind freshly collected devotional passages to their independent review.
# Return usable records and file hashes; held interpretations remain excluded.
# Missing, changed or incompletely reviewed files raise before live setup.
def devotional_library(work):
    supplement, source_hash = load(work / 'evidence-devotional-supplement.json')
    review, review_hash = load(work / 'evidence-devotional-independent-review.json')
    if (review.get('gate') not in ('PASS', 'PASS_WITH_LIMITS', 'PASS_WITH_EXPLICIT_QUALIFICATIONS')
            or review['reviewed_file']['sha256'] != source_hash
            or review.get('unresolved_required_corrections')):
        raise ValueError('Devotional supplement requires exact independent clearance')
    decisions = {row['id']: row for row in review['per_record']}
    records = supplement['records']
    if (len(decisions) != len(review['per_record'])
            or set(decisions) != {row['id'] for row in records}):
        raise ValueError('Devotional supplement review coverage incomplete')
    library = []
    for row in records:
        disposition = decisions[row['id']]['disposition']
        if disposition == 'HOLD':
            continue
        if disposition != 'USABLE' or row['blockers'] or row['attestation_status'] != 'ATTESTED_PRIMARY_ONLINE_TEXT':
            raise ValueError('Unusable devotional evidence cannot advance')
        if hashlib.sha256(row['original_passage'].encode()).hexdigest() != row['passage_sha256']:
            raise ValueError('Devotional passage bytes changed')
        library.append({'source_id': row['id'], 'source_sha256': source_hash,
                        'location': row['locator'], 'canonical_passage': row['original_passage'],
                        'passage_sha256': row['passage_sha256'], 'title': row['work'],
                        'meaning_mr': row['faithful_meaning_mr'],
                        'context_mr': {'original_context': row['context_mr'],
                                       'limits': row['meaning_limits_mr']},
                        'eligible': True, 'verified': True, 'source_record': row,
                        'verification_record': decisions[row['id']]})
    if not library:
        raise ValueError('No independently usable devotional supplement')
    return library, {'devotional_supplement': source_hash, 'devotional_review': review_hash}


# Verify current implementation has recorded offline evidence, then prepare a
# deterministic two-pair calibration followed by stable cost-saving batches.
# Returns a bound plan. Missing/stale tests or references fail before API setup.
def prepare(work=WORK):
    work = Path(work)
    tests, _ = load(work / 'offline-test-results.json')
    if tests.get('status') != 'PASS_OFFLINE_ONLY':
        raise ValueError('Offline test gate has not passed')
    hashes = tests.get('current_code_hashes', tests['code_hashes'])
    for name, expected in hashes.items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected:
            raise ValueError('Implementation changed after its offline test evidence')
    manifest = verified_manifest(work)
    candidates, sources = primary_inputs(manifest)
    library, input_hashes = verified_library(work)
    devotional, devotional_hashes = devotional_library(work)
    library.extend(devotional)
    input_hashes.update(devotional_hashes)
    sources.update(input_hashes)
    sources.update({row['source_id']: row['source_sha256'] for row in library})
    sources['candidate_manifest'] = load(work / 'candidate-manifest.json')[1]
    size = min(20, 1000 // len(library))
    if size < 1:
        raise ValueError('Evidence corpus exceeds the bounded batch contract')
    batches = [candidates[:2]] + [candidates[start:start + size]
                                for start in range(2, len(candidates), size)]
    # Validate every batch before any paid setup, not only the first calibration.
    # This catches registry aliasing and late-candidate drift without API cost.
    for index, batch in enumerate(batches):
        prepare_research_batch(f'research-{index + 1:03d}', batch,
                               pair_evidence(batch, library), sources)
    plan = {'status': 'PREPARED_NOT_LIVE', 'candidate_count': len(candidates),
            'reference_count': len(library), 'source_hashes': sources,
            'candidates': candidates, 'library': library,
            'batches': [[row['id'] for row in batch] for batch in batches],
            'author_approval': 'PENDING', 'new_sutras': 0}
    plan['plan_sha256'] = digest(plan)
    return plan


# Explicit live execution; returns research gates and persists every batch.
# Only the first calibration batch runs unless all_batches=True. Existing paid
# successes require explicit resume=True and exact frozen requests; failures
# stop rather than repeat. No council composition or publication occurs here.
def run(plan, work=WORK, *, live=False, all_batches=False, resume=False, recover_timeout=False):
    work = Path(work)
    if recover_timeout and not (live and resume):
        raise ValueError('Timeout correction requires explicit live resume')
    diagnostic = None
    if recover_timeout:
        diagnostic, diagnostic_hash = load(work / 'timeout-correction-diagnostic.json')
        review, review_hash = load(work / 'timeout-recovery-independent-review.json')
        if (diagnostic.get('status') != 'OFFLINE_VERIFIED_CONFIGURATION_CORRECTION'
                or diagnostic.get('independent_review_status') != 'PASS'
                or diagnostic.get('independent_review_sha256') != review_hash
                or review.get('gate') not in ('PASS', 'PASS_WITH_LIMITS')
                or review.get('unresolved_required_corrections')):
            raise ValueError('Timeout correction has not independently passed')
    save_bound(work / 'research-stage-plan.json', plan)
    if not live:
        return {'status': 'OFFLINE_PREPARED', 'candidates': plan['candidate_count'],
                'references': plan['reference_count'], 'paid_calls': 0}
    provider = create_live_provider(work / 'research-provider',
        credentials_dir=Path('C:/Users/LENOVO/Dropbox/Hiranyam AI Labs/SK_Udyog_Sutras'),
        source_hashes=plan['source_hashes'], max_usd=20., max_calls=80,
        claude_cap_usd=15., enable_live=True, resume=resume)
    provider.adapters['researcher'].effort = 'low'
    # Match the established five-agent runner's bounded network allowance.
    # Network timeout does not increase output tokens or change a model.
    for adapter in provider.adapters.values():
        adapter.timeout_seconds = 240.
    if recover_timeout:
        provider.authorize_timeout_correction('researcher', diagnostic['failed_stage'],
            diagnostic['replacement_stage'], diagnostic['failed_request_sha256'], diagnostic_hash)

    def dispatch(voice, stage, system, payload, tokens):
        """Resolve only a previously authorized stage alias; no implicit retry.

        Return the unchanged boundary's parsed response. Failed or drifted calls
        remain stopped; source, budget and raw-response checks remain mandatory.
        """
        return call_with_lossless_framing(provider, voice, provider.resolve_stage(voice, stage),
                                          system, payload, tokens)
    candidates = {row['id']: row for row in plan['candidates']}
    completed = []
    for index, identifiers in enumerate(plan['batches']):
        if index and not all_batches:
            break
        if index and not completed[0]['supported_and_reviewed']:
            raise ValueError('Calibration produced no independently supported case; inspect before spending more')
        batch = [candidates[identifier] for identifier in identifiers]
        result = screen_batch(f'research-{index + 1:03d}', batch,
            pair_evidence(batch, plan['library']), plan['source_hashes'], dispatch,
            work / 'research-screening', research_tokens=max(8000, len(batch) * 1200 + 4000),
            review_tokens=max(3000, len(batch) * 350))
        completed.append(result)
        print(f"RESEARCH BATCH {index + 1} screened={len(batch)} supported={len(result['supported_and_reviewed'])}", flush=True)
    report = {'status': 'SCREENING_COMPLETE' if all_batches else 'CALIBRATION_SCREENED',
              'plan_sha256': plan['plan_sha256'], 'batches': completed,
              'provider_calls': provider.dispatcher.calls,
              'reserved_usd': provider.dispatcher.reserved_usd,
              'reservation_is_not_actual_invoice': True, 'author_approval': 'PENDING', 'new_sutras': 0}
    save_bound(work / ('research-full-report.json' if all_batches else 'research-calibration-report.json'), report)
    return report


# Parse explicit preparation/live/resume controls. Errors remain visible and
# no user approval is inferred from a document or a successful test run.
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--all', action='store_true', dest='all_batches')
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--recover-timeout', action='store_true')
    args = parser.parse_args()
    report = run(prepare(), live=args.live, all_batches=args.all_batches, resume=args.resume,
                 recover_timeout=args.recover_timeout)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
