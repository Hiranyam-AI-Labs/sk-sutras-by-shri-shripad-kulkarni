"""Source-first council prompt/acceptance adapters; no providers or new formulas.

Reuse the tested four-voice council and independent validator. Canonical full
packets stay checkpointed; paid model views omit internal audit bulk only.
"""
from copy import deepcopy

from scripts.run_research_book import SYSTEM, prompt_payload, stage_contract
from src.orchestration.research_acceptance import assess_research_entry


WRITING_SYSTEM = SYSTEM + """
SOURCE-FIRST PRIORITY: the original Narada and Shandilya devotional meanings
are the foundation, not citations attached after an MBA-style business lesson.
Explain both source propositions and the researcher's genuinely supporting or
qualifying passage before deriving a clearly labelled modern business extension.
The supplied business brief is a hypothesis, not an instruction to force a fit.
All four voices question each other. Sutrakar may explicitly reject a candidate
after that discussion; writing a formula is never required for a rejected case.
Accepted formulas must stay short, faithful and practical. Keep the devotional
warmth, service, care and integrity where the actual sources justify them; do
not equate God with profit or claim spiritual immortality means business success.
No invented quotes, cases, motives or causes. Keep original source meaning and
modern interpretation distinct throughout. Grammar and reader-facing explanation
remain clear Marathi; no English translation. Publication and author approval
always remain pending.
"""


# Reduce a source packet to substantive model evidence and qualifications.
# Return a copy, preserving canonical references/examples/context/fit reasons.
# Missing optional metadata is harmless; required evidence is gated elsewhere.
def lean_packet(packet):
    result = {key: deepcopy(packet[key]) for key in
              ('references', 'examples', 'source_pair_ids', 'pair_reference_ids',
               'source_contexts', 'pair_contexts', 'research_fit', 'source_pair',
               'research_interpretation', 'business_limits_mr') if key in packet}
    if 'source_contexts' in result:
        contexts = {}
        for identifier, context in result['source_contexts'].items():
            contexts[identifier] = {key: deepcopy(context[key]) for key in
                ('id', 'sanskrit', 'meaning_mr', 'context_mr', 'source_note', 'original_iast',
                 'canonical_passage', 'location', 'source_id', 'title') if key in context}
            source = context.get('source_record', {})
            limits = {key: deepcopy(source[key]) for key in
                ('meaning_qualifications_mr', 'meaning_limits_mr', 'context_mr', 'source_qualifications')
                if key in source}
            if limits:
                contexts[identifier]['source_qualifications'] = limits
        result['source_contexts'] = contexts
    provenance = packet.get('selection_provenance', {})
    card = provenance.get('selection_card', {})
    if card:
        result['editorial_hypothesis'] = {key: deepcopy(card[key]) for key in
            ('topic_mr', 'decision_mr', 'action_mr', 'source_derivation_mr', 'journey_stage')
            if key in card}
    representative = provenance.get('representative', {})
    research = representative.get('research', {})
    if research:
        result['research_interpretation'] = {key: deepcopy(research[key]) for key in
            ('candidate_id', 'source_core_mr', 'relation_kind', 'relation_mr',
             'limitations_mr', 'business_extension_mr', 'evidence_ids') if key in research}
    if packet.get('case_assignments'):
        result['case_fit'] = [{key: deepcopy(case[key]) for key in
            ('kind', 'case_id', 'fit_reason_mr', 'limitations_mr') if key in case}
            for case in packet['case_assignments']]
    return result


# Compact an already checkpointed council payload while retaining all four
# voices' current-entry discussion and canonical source/case text. Return a
# model view; no source hashes or successful checkpoints are changed.
def writing_view(payload):
    value = prompt_payload(payload)
    if payload.get('scope') == 'batch':
        value['sources'] = {key: lean_packet(packet) for key, packet in value['sources'].items()}
        briefs = value.get('briefs', [])
    else:
        value['sources'] = lean_packet(value['sources'])
        briefs = [value.get('brief', {})]
    for brief in briefs:
        brief.pop('selection_provenance', None)
    return value


# Add explicit accepted/rejected source-first schemas to the existing contracts.
# Return one instruction string; unknown stages still fail via the old contract.
# This adapter changes no roles, models, evidence or validator contract.
def writing_contract(kind, payload):
    if kind == 'proposal' and payload.get('scope') == 'batch':
        return ("Return {proposals:[...]} with exactly one record for each entry number "
                + str(payload['entry_numbers']) + ". Sutrakar must arbitrate the four voices. "
                "Accept only a natural source-first derivation: {number,decision:'ACCEPT',"
                "proposed_sutra,derivation,selected_source_ids}. Formula2-4words and<=32Unicodecharacters. "
                "selected_source_ids must include BOTH source_pair_ids and at least one genuinely "
                "relevant supplied supplementary reference. Derivation max60words, preserving source "
                "meaning and interpretation limits. Reject when fit is weak: {number,decision:'REJECT',"
                "rejection_reason}, at least five substantive words and NO proposed_sutra. "
                "Do not invent a formula or force citations for a rejected case.")
    instruction = stage_contract(kind, payload)
    if kind == 'peer_review' and payload.get('scope') == 'batch':
        instruction += (" For a REJECT proposal, assess the evidence-based rejection reason; "
                        "absence of proposed_sutra is required, not a defect. Anchor any issue "
                        "to an actual current field such as rejection_reason.")
    if kind == 'composition':
        instruction += (" Include BOTH source_pair_ids in references and comparative_mr, plus "
                        "at least one defensible supplied supplementary reference. Main exposition "
                        "must grow from those devotional meanings, not retrofit them to a generic "
                        "business chapter. Keep source briefs concise, business exposition substantive.")
    return instruction


# Check an accepted short proposal before paying for a long composition.
# Return None; missing pair or supplementary IDs raises without any model call.
# Rejections are handled by the council's opt-in disposition gate.
def require_proposal_support(proposal, packet):
    pair = set(packet['source_pair_ids'])
    selected = proposal.get('selected_source_ids', [])
    registered = {reference['id'] for reference in packet['references']}
    if (proposal.get('decision') != 'ACCEPT' or not isinstance(selected, list)
            or any(not isinstance(identifier, str) for identifier in selected)
            or not pair.issubset(selected) or not set(selected).issubset(registered)
            or not (set(selected) - pair)):
        raise ValueError('Accepted source-first proposal requires both sutras and supplementary support')


# Add composition-level foundation checks to the existing structural assessor.
# Return a normal assessment; missing original-source briefs or supplementary
# support hold the entry. Semantic truth still belongs to independent review.
def assess_source_first_entry(entry, packet, prior, forbidden, used):
    result = assess_research_entry(entry, packet, prior, forbidden, used)
    entry = entry if isinstance(entry, dict) else {}
    pair = set(packet.get('source_pair_ids', []))
    selected = entry.get('references', [])
    valid_selected = isinstance(selected, list) and all(isinstance(identifier, str) for identifier in selected)
    selected_set = set(selected) if valid_selected else set()
    comparisons = entry.get('comparative_mr', [])
    comparisons = comparisons if isinstance(comparisons, list) else []
    compared = {row.get('source_id') for row in comparisons
                if isinstance(row, dict) and isinstance(row.get('source_id'), str)}
    issues = list(result['issues'])
    if len(pair) != 2 or not valid_selected or not pair.issubset(selected_set):
        issues.append('Both canonical Narada/Shandilya references must remain in the composition')
    if not pair.issubset(compared):
        issues.append('Both canonical source sutras require concise Marathi source explanations')
    if not valid_selected or not (selected_set - pair):
        issues.append('Source-first composition lacks selected supplementary research support')
    return {**result, 'issues': issues, 'status': 'PASS' if not issues else 'NEEDS_REVISION'}
