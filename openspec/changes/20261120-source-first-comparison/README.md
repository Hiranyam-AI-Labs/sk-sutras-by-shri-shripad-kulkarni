# Source-first Narada–Shandilya comparison

Status: approved approach; source correction in progress. No completed comparison or score report is claimed.

## Authorized scope and preserved assets

The user resumed on 20 November 2026 and approved source correction first, followed by exhaustive semantic comparison and a simple Marathi PDF report. Preserve original supplied documents, existing manuscripts, all five production roles and their model assignments. Paid generation remains stopped; the current source/comparison work uses no customer LLM API keys. This change does not authorize publication or author approval.

## Acceptance specification

1. Establish a provenance-bearing working source. The published editions currently contain 84 Narada and 100 Shandilya sutras, but the user explicitly accepts the actual defensible counts after correction rather than requiring a fixed pair count. Distinguish consequential errors from supported edition variants. Preserve original readings, disclose working corrections and uncertainties. Independently review every corrected Shandilya entry before scoring. Replace spurious repetitions with the proper published entries where supported; do not delete distinct canonical entries merely for similar meaning. Record any excluded/unresolved entry and its reason.
2. Enumerate every unique ordered cross-text pair from the final comparison-eligible sets, with coverage evidence: actual Narada count multiplied by actual Shandilya count (8,400 only if 84 and 100 remain eligible). Each eligible Narada entry is compared with every eligible Shandilya entry. Never remove a sutra from consideration because it already has another match. Enumerating pairs is not semantic assessment. Report excluded source entries separately so a reduced count cannot conceal incomplete source review.
3. Resolve contextual pronouns, argument sequence, objections and answers before assessing similarity. Each assessment records the two source IDs, original text, accessible Marathi meaning, four component scores, rationale, differences, relation type, uncertainty and review status. No generic keyword-only scoring or fabricated confidence percentages.
4. Similarity rubric: main meaning 0–40; precise proposition 0–25; original context/purpose 0–20; conditions/limitations 0–15. These are interpretive rubric points, not calibrated probabilities. Allow half-points; the earlier provisional five-point-only suggestion is superseded by the user's component thresholds.
5. Primary eligibility requires all of: total >=60, meaning >=30, proposition >=12.5, context >=10, conditions >=7.5. An invalid source, unresolved material contradiction, or forced linkage blocks progression regardless of the arithmetic.
6. Reserve list: 50 <= total <60, descending total. Preserve original component scores and failed thresholds. Use only if the primary path yields materially fewer than approximately 100 suitable distinct sutras. Reserve progression is an explicit exception to primary score/component eligibility, never an exception to source integrity, defensible meaning, research, Sutrakar challenge or independent validation. Total >=60 with a failed component remains component-rejected, not silently reserve-eligible. Ties may remain equal; do not invent precision.
7. Pair similarity is separate from business usefulness. Multiple pairs may support one distinct lesson; no one-pair/one-chapter assumption or repeated lessons merely to increase the count.
8. Eligible pairs pass to the researcher for relevant available Vedic, Upanishadic, Gita, saint-literature and author-document evidence. Record the exact supporting passage and provenance; do not require every text to support every pair or treat contemporary author interpretation as independent ancient evidence.
9. Four voices deliberate. Narada and Shandilya explain source meanings; the researcher supplies/challenges supporting evidence. Sutrakar questions all three, arbitrates the pairing and research fit, rejects weak combinations and writes the new short business sutra and explanation only for defensible selections. No forced matching at any stage.
10. The fifth validator remains independent. Check original source meaning, claimed connections, factual attribution, Sanskrit grammar, Marathi translation/explanation, real verified business examples and book-wide duplication. Passing means ready for author review, never automatic author approval.
11. Approximately 100 useful distinct entries is an aspiration, not a quota. More or fewer are allowed. The approved book format, protected first nine pages and established closing pages remain requirements for any later book build. No rewriting those assets during this comparison task.

## Current evidence and next checks

- [Source audit](../../../logs/20261119-sutra-comparison/source-audit-shandilya.json): supplied DOCX has 72 material same-number discrepancies; repository JSON has 97. These include relocation, substitutions and omissions, not a claim that every underlying idea is false.
- [Working Shandilya corpus](../../../logs/20261119-sutra-comparison/shandilya-working.json): being completed and independently reviewed; file existence is not acceptance.
- Shandilya working-source review: PASS_WITH_EXPLICIT_UNCERTAINTIES, all100 entries, final source hash verified;42 contextual uncertainties retained. Narada all84 independent review also PASS_WITH_EXPLICIT_QUALIFICATIONS, zero material fixes required. Both final file hashes verified in source-gate.json.
- Bounded Narada2 x100 independent calibration PASS after one wording correction, scores unchanged. Pilot48-page Marathi PDF delivered after all-page visual QA;3primary,13reserve,5component-rejected,77belowthreshold,2blocked.
- All8,400 pair assessments now have independent PASS reviews bound to final draft hashes. The final coverage/threshold audit reports8,400 unique pairs, no missing pairs:243primary,758reserve,211component-rejected,7,091belowthreshold,97blocked. These are source-pair classifications, not generated business chapters or scholar certification. Final PDF assembly/rendering and delivery QA remain pending.
- Research/Sutrakar/full generation: not run under this change.

Implementation order: source integrity → independent working-corpus review → explicit rubric anchors and one-by-100 calibration → all-pairs assessment and independent checks → coverage/count audit → rendered and visually verified Marathi PDF → evidence-backed handoff to the remaining stages. No score changes solely to meet the desired manuscript count.

### Offline rule verification

Eight synthetic threshold and coverage checks passed: inclusive60; failedcomponent despitehightotal; reserve55; below50; forcedconnection blocker; pendingreview; missingpaircoverage; duplicatepairrejection. Evidence: [threshold-checks.json](../../../logs/20261119-sutra-comparison/threshold-checks.json). These checks establish arithmetic/control behavior only, not source or semantic correctness. Task-local audit helper is not integrated into the production runner.

Independent source evidence: [Shandilya review](../../../logs/20261119-sutra-comparison/shandilya-working-review.json). Five findings resolved and rechecked. The review also corrects an earlier audit note: the rice/husking analogy is present in Sivananda commentary on16 as well as27; do not use that earlier negative attribution. The72/97 same-number text-discrepancy counts are unaffected. AI-reviewed working corpus, not scholarcertified.

Pilot delivery evidence: [QA receipt](../../../logs/20261119-sutra-comparison/pilot-delivery-qa.json); [reviewed pilot PDF](../../../deliverables/20261120-source-comparison/Narada_02_Shandilya_100_Comparison_Marathi.pdf). Four assessors and two independent reviewers are assigned in [work-assignments.json](../../../logs/20261119-sutra-comparison/work-assignments.json). Saved draft rows are not accepted comparison results.
