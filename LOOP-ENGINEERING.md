# Engineering loop index

## 2026-11-16 — chapter 2 reader presentation

- User requested new sutra and accessible Marathi explanation first, brief
  source links afterward, and removal of grammar, AI history and repeated
  technical caveats. Opening pages 1–9 must remain intact.
- Added an explicit reader presentation option to the Word exporter and an
  offline chapter-2 editorial script. The 553-word explanation keeps the
  opening business journey, focus, responsibility, employee cooperation,
  learning and the transition toward vision and purpose. Examples appear once.
- Verification: 12 affected offline tests passed. The reader Word file renders
  to 15 pages; its first 12 pages match the original at 72 DPI. New pages were
  visually inspected. Source passages and the short Sanskrit sutra are retained.
- No paid calls, new chapters, human approval or publication. This is an edited
  reader draft of the pilot; prior scholarly review concerns are not resolved
  by presentation changes.

## 2026-11-16 08:36 IST — 20261115-author-v19-book — chapter 2 short-sutra pilot

- Authorization and scope: user approved chapter 2 only under a $1 estimated
  reservation cap, with the result to be shown before any later chapter. The
  four-agent discussion and peer reviews were reused from saved evidence;
  the existing Claude Sutrakar and GPT validator models made the new calls.
- Preparation: added a default read-only plan and an explicit `--execute`
  single-chapter repair script with exact request checkpoints. The original
  chapter and book are never overwritten. The affected offline suite passed
  43 tests before the live call; `git diff --check` exited 0.
- Live evidence: four successful dispatch calls, $0.3624765 in estimated
  reservations against the $1 ceiling. Actual billing is unknown. Two Sutrakar
  candidate rounds and two independent review rounds produced a selected
  22-character, two-word sutra with 664 Marathi explanation words. The
  deterministic gate passed, but the independent verdict is `REVIEW_REQUIRED`
  with seven items. Some require source and Sanskrit review; one objection
  mentions a form absent from the selected sutra and needs triage.
- Artifact QA: the separate 16-page chapter-2 pilot Word excerpt preserves
  authored pages 1–12 pixel for pixel at 72 DPI; all four new pages were
  inspected. Only seven linked chapter text fields changed. Source sutras,
  examples and the original chapter-2 JSON remain unchanged.
- Delivery state: offline pilot DRAFT only. No author approval, publication,
  replacement of the full book, or chapter-3 execution. Await the user's
  assessment of the sample's style and validator concerns.

## 2026-11-15 23:42 IST — 20261115-author-v19-book — short-sutra gate correction

- Failure: the delivered local draft's 19 new Sanskrit lines are 49–77 Unicode
  characters (median 68), while the available authored v19 examples are 19 and
  28. The 80-character acceptance rule and proposal-stage prompt permitted
  multi-clause, procedural verses; the final audit reused that weak rule.
- Correction: the working acceptance gate is now two to four words and at most
  32 characters excluding verse delimiters. Proposal, composition and
  independent-review prompts state the same rule. Council proposal and
  composition stages reject overlong answers locally; a failed proposal gets
  at most one correction attempt and stops before peer review or full draft.
  The Word exporter refuses long verses before saving an output file.
- Verification: the corrected read-only audit found 19 draft files and 19
  failures under the shortness gate. The focused book test suite passed 10
  tests and the affected offline suite passed 42 after fixture correction. No
  paid API calls, manuscript replacement, approval or publication occurred.
- Next: finish offline tests, preserve the old book as a rejected checkpoint,
  then use saved four-agent discussion for a targeted short-verse repair with
  Sutrakar and independent validator only after the user reviews the expected
  extra spend. Recheck Sanskrit and linked explanations before author review.

## 2026-11-15 23:00 IST — 20261115-author-v19-book — 20-sutra completion

- User changed the maximum from 25 to 20 total sutras and requested a gradual
  closing arc in chapters 16–20. The roadmap, runner, exporter and audit now
  enforce that cap. Existing five agent roles and provider/model assignments
  stayed fixed; the four council roles continued challenge and reply rounds,
  with an independent fifth review.
- Anthropic credits were restored. A direct peer-keyed provider reply at
  chapter 15 required normalization before resuming from saved stages. The
  affected offline suite passed 41 tests after that repair. The full repository
  suite still has the previously recorded eight unrelated failures.
- The paid run completed chapters 2–20. The book-wide audit returned
  `READY_FOR_AUTHOR_REVIEW`, 19 new chapters, no structural issues, and no
  automatic human approval or publication. All 19 independent verdicts remain
  `REVIEW_REQUIRED`; chapter 18's Sanskrit/action clarity and chapter 20's
  source numbering and closing guidance are explicit human-review items.
- Word rendered the 20-sutra draft as 100 pages. Pages 1–12 matched the author
  original pixel for pixel at 72 DPI. Contact sheets covered generated pages
  13–100 with no observed clipping; closing pages were checked at higher
  resolution. Nineteen new headings, no reader-facing internal source IDs or
  hashes, and no doubled verse delimiters were found.
- The local ledger has 595 cumulative provider calls and $78.52 in estimated
  reservations across book work, including earlier attempts. Actual provider
  billing is unknown. The Word file and evidence remain local DRAFT artifacts
  awaiting author and Sanskrit-scholar review.

## 2026-11-15 21:30 IST — 20261115-author-v19-book — iterations 9–11

- Objective and acceptance: `openspec/changes/20261115-author-v19-book/README.md`;
  25 total sutras maximum, all four council roles replying to every peer,
  independent fifth review, readable author-format Word draft and no automatic
  human approval.
- Inputs: author v19 Word original, saved chapter JSON and exact local SQLite
  stage/call audit under ignored `logs/book-v19/`. The roadmap has exactly 25
  entries. No credential values were written to evidence or Git.
- Root cause and correction: chapter 14's Narada reply omitted Shandilya.
  The council now rejects replies without all three peer IDs, the runner asks
  for explicit peer-keyed replies, and the audit checks saved transcripts.
  The chapter 14 draft and database were archived; only its dependent stage
  records and chapter 15 dependent positions were invalidated. All paid-call
  audit records remain. The next call stopped at chapter 15 because Anthropic
  returned HTTP 400, credit balance too low; model substitutions are excluded.
- Word refinement: new headings have one verse delimiter pair; internal DOC
  IDs and source SHA fingerprints are rendered as readable source names only
  in the Word display. Explanation blocks use separate author-style bullet
  paragraphs, avoiding stretched spaces from manual line breaks. Raw draft
  and source audit evidence remain unchanged.
- Verification: repository root, `.venv/Scripts/python.exe -B -m pytest
  tests/test_book_v19.py tests/test_source_evidence.py tests/test_council_service.py
  tests/test_dispatch.py tests/test_live_runner_wiring.py -q -p no:cacheprovider
  --basetemp logs/book-v19-test-tmp-34` — exit 0, 40 passed. Focused Word tests
  after display cleanup — exit 0, 9 passed. Full `pytest tests` — exit 1,
  126 passed and 8 failed in legacy credentials, Chroma and a hardcoded
  previous-machine Word output test; these are not claimed as a pass.
- Artifact and page review: active local Word draft has authored sutra 1 plus
  new sutras 2–13, 66 Word-rendered pages. Pages 1–12 match the original
  pixel for pixel at 72 DPI, exceeding the required untouched pages 1–9.
  Contact sheets cover all 54 generated pages, with no observed clipping;
  the cleaned Word text has 13 headings and no internal DOC IDs or hashes.
  `audit_book(..., expected_total=13)` returned no issues; the approved target
  of 25 remains incomplete. Chapter 14's prior version is archived locally.
- Delivery: local unapproved checkpoint only; no publication, approval,
  deployment, commit or push. Git author identity is unset. Resume the exact
  chapter 14 discussion after Anthropic workspace credits are restored,
  complete through chapter 25, rerun affected checks and render/audit the
  final book before author and Sanskrit-scholar review.

## 2026-11-15 20:05 IST — 20261115-author-v19-book — iterations 1–8

- Objective and acceptance: `openspec/changes/20261115-author-v19-book/README.md`;
  25 total sutras maximum, four reciprocal discussion agents, one independent
  validator, original first nine pages, Marathi business guidance and distinct
  positive/cautionary cases.
- Inputs: author v19 DOCX at the user-supplied path; registered DOC-01 through
  DOC-04 extracts, Narada and Shandilya JSON, local ignored council ledger.
  The four registered source hashes were reconciled to corrected local extracts.
- Change: resumable book council, source-grounded researcher, deterministic
  chapter checks, original-style Word export and read-only book audit. Existing
  provider/model assignments and human approval boundary are retained.
- Verification: repository root, `.venv/Scripts/python.exe -B -m pytest
  tests/test_book_v19.py tests/test_source_evidence.py
  tests/test_council_service.py tests/test_dispatch.py
  tests/test_live_runner_wiring.py -q -p no:cacheprovider
  --basetemp logs/book-v19-test-tmp-24` — exit 0, 38 passed.
  The same affected suite passed again after Devanagari numbering; exit 0,
  38 passed. Installed Word exported the pilot for visual comparison; rendered
  pages 1–9 matched the author original pixel for pixel at 72 DPI. LibreOffice
  is absent; Word COM was used without saving the original.
- Root causes and corrections: malformed challenge JSON was normalized while
  requiring all three peer critiques; long research/peer replies received
  concise prompts and larger output reservations; SDK imports were serialized
  before concurrent turns. The validator's stale-proposal objections were
  separated from deterministic draft acceptance. Template cloning now keeps
  red labels and black body prose. Missing cautionary cases, overly long
  Sanskrit lines, stale source fingerprints and dependent resume checkpoints
  were corrected and retested.
- Live evidence: chapter 2 and chapter 3 are locally stored and pass
  deterministic book checks; both remain REVIEW_REQUIRED at the independent
  scholarly gate. Chapter 3's Sanskrit line was shortened from 111 to 72
  characters. Complete role transcripts, chapter JSON, local Word draft,
  sanitized provider audit and run reports are under ignored `logs/book-v19/`.
  Final 25-sutra completion is pending; the full generation is in progress.
- Documentation/output: active OpenSpec change and this loop entry updated;
  earlier failed attempts remain in local logs. No author approval, public
  export, deployment or invoice-cost claim.
- Delivery: local draft only; no commit or push yet. Next: monitor the full
  run, resolve any diagnosed failure, rerun affected checks, audit all
  chapters, render and inspect the final Word pages, then submit for author and
  Sanskrit-scholar review.

## 2026-11-14 IST — 20261114-fifteen-gate-council — reliability iteration 1

- Objective: R-01 through R-05 in `openspec/changes/20261114-fifteen-gate-council/README.md`.
- Inputs: baseline eb71629; modified implementation/test set and hashes in local ignored
  `logs/reliability-pilot/tested-inputs.json`.
- Capabilities: governance, workflow, database. Existing Python/SQLite/provider toolchain reused.
- Correction: persist before verification; exact request resume; bounded paid continuation;
  eight-stage preflight; enroll sourced principal identities pending humans.
- Verification: established focused regression command in `docs/RELIABILITY_FIXES_20261114.md`,
  repository root, exit 0, 62 passed; follow-up targeted suite exit 0, 31 passed. No live result is inferred from fake responses.
- Live gate: BLOCKED. Automatic review rejected process creation pending explicit
  authorization for the exact external manuscript/source payload. No paid call occurred.
- Outputs: engineering report and active OpenSpec updated; customer rendering unchanged.
- Reuse/reflection: reuse existing dispatcher/checkpoint/store rather than another runner.
- Delivery: scoped changes staged; commit BLOCKED because Git user.name/user.email are unset. No global configuration or author identity was invented. No push/deployment/publication.
- Next action: obtain external-payload authorization, run the bounded local pilot,
  inspect real draft/gates and iterate only after a diagnosed correction.


## 2026-11-14 IST — 20261114-fifteen-gate-council — reliability iteration 2

- User authorized the exact external-processing action, retaining generated drafts locally.
- Live failure: opening candidate copied a prior formulation; source pairing was rejected.
- Correction: retain full canonical Narada in downstream roles and author/verifier evidence;
  provide existing formulations; make used-identity exclusions explicit.
- Verification: final established 11-module regression suite, exit 0, 64 passed;
  log `logs/reliability-pilot/final-tests.log`, current input hashes in `tested-inputs.json`.
- Live result: 30 successful calls; USD 2.71725725 new reservations, USD 4.34144425 including
  prior ledgers, same durable deadline. No cap/deadline reset. Invoice cost unknown.
- Output: one new UDYAM-2 chapter in three unapproved versions, plus rejected UDYAM-1.
  V2 is assessed: seven PASS/eight HUMAN_REVIEW_REQUIRED/no FAIL. Final v3 persisted
  when the validator was blocked before dispatch by the call cap.
- Evidence/export: exact stored JSON and UTF-8 author-review copies under ignored
  `logs/reliability-pilot/`; see `docs/RELIABILITY_FIXES_20261114.md` for exact counts.
- No human approvals, publication manifests, deployment or external manuscript hosting.
- Delivery: scoped implementation staged; commit identity remains unset; no push.
- Next: author/scholar review and source registration. Generation is demonstrated;
  all-gate quality acceptance is pending and is not substituted by synthetic tests.


## 2026-11-16 Offline author-source consolidation review draft

Scope: consolidate the author's 28-sutra edition, 50-sutra PDF conversation and 105-sutra edition. New sutra generation remains paused. No paid API calls, agent/model changes, approval or publication.

Result: separate 100-entry Word review draft across 20 chapters, with concise Marathi explanations, practical guidance and 200 distinct example texts (11 sourced factual cases; 189 explicitly fictional illustrations). All 106 numbered records in the extended edition and all 28 earlier records are mapped in the selection evidence. Six overlapping extended-edition records were merged. Sixteen short formulations have logged local corrections or excerpts.

Verification: assembler exit 0; Word read-only PDF export exit 0, 115 pages; page-render verifier exit 0. First nine pages and selected closing page match reference renders pixel-for-pixel. No sparse/blank output pages. Original source hashes unchanged. Protected opening XML and unchanged package parts pass comparison. A separate local closing style and 2pt section-start compensation preserve the reference appearance. Iterations fixed namespace-sensitive audit comparison, closing alignment, an appendix blank page, and Marathi wording.

Evidence and reproducibility: [artifact contract](logs/author-consolidation-20261116/artifact.md), [builder](logs/author-consolidation-20261116/assemble_book.py), [manifest and per-entry provenance](logs/author-consolidation-20261116/consolidation_manifest.json), [render evidence](logs/author-consolidation-20261116/render_verification.json). The manifest records the delivery copy and SHA-256.

Limits: AUTHOR_REVIEW_PENDING. Sanskrit formulations and interpretations require author/scholar approval. Unverified ancient-source pairings were omitted, not invented. The fictional-example policy is explicit. Explanations are concise editorial notes, not the paused 500-word generation workflow. Protected original closing claims remain unchanged. No application release, security certification, deployment, Git publication, or author approval is implied.

## 2026-11-17 Author-directed manuscript revision awaiting recording

The client rejected the prior compilation. User requires verified distinct real business examples, the newly supplied author 100-sutra manuscript as content basis, three Narada/Shandilya sources, and strict new-folder V19 formatting including grammatical technicalities. First nine physical pages and the previously agreed complete closing section remain protected. No API calls or new sutra generation. Manuscript revision is intentionally pending the author's promised recording. Only filenames were inventoried and instructions recorded; no manuscript changed.

Durable instructions and exact filenames: [revision instructions](logs/author-revision-20261117/user-instructions.json). Earlier removal of grammar notes and use of fictional illustrations are superseded. This record does not approve or publish any manuscript.
## 2026-11-17 — Author materials and Marathi call: approval-stage review

Scope: analyze all six documents in the user's 17Nov2026 directory and the 31:04 Marathi recording, then propose the editorial specification. User explicitly requires approval before book editing/compilation. New generation remains paused; no paid LLM/transcription API calls, agent/model changes, manuscript edits, publishing or approval.

Loop: extracted and reviewed documents, visually inspected scanned reference pages, compared source texts, catalogued 100 numbered entries, identified semantic-overlap and grammar/source flags, and checked a representative business claim against primary Tata sources. Local transcription trials exposed repetition/omission errors; rejected outputs were retained as diagnostics, not accepted as author quotations. Isolated runtime fixes and a Marathi-specific comparison were used; no application dependencies were changed. Final full-duration machine pass contains 65 timestamped segments and seven sparse segments flagged for review.

Verification: all seven original file SHA-256 hashes match the initial inventory; candidate matrix has 100 rows; transcript timestamps are chronological through 31:04.38. No verified verbatim transcript or word-error-rate claim is made. The raw transcript has substantial recognition errors and omissions. Readable Marathi notes are explicitly paraphrases; uncertain audio was not used to invent requirements.

Artifacts: logs/author-revision-20261117/Review_and_Acceptance_Specification.txt; Call_Analysis_Marathi.txt; Call_Transcript_Machine_Draft.txt; Transcription_Quality_and_Status.json; Candidate_Review_Matrix.json; Originals_Unchanged_Verification.json. Durable user-instructions.json updated.

Result: document review and proposed acceptance plan ready for user review. Manuscript activity AWAITS_USER_APPROVAL. Exact verbatim transcription remains unverified and requires human correction before quotation. Source-edition integrity, substantive Sanskrit corrections, attribution policy and protected closing/count/appendix conflicts are explicit decisions. No commit, push, publication or release.

## 2026-11-17 — Author final master prompt incorporated into proposed plan v2

Read Udyamasutre_Final_Master_Prompt.docx completely (189 body paragraphs plus header/footer, no media or embedded working copy). SHA-256 remains 5e8db564bb5cc4f2959fe39bc8df557f8355ff65b69a4222cc5f5d8c209b0115. No original changed.

Reconciled the explicit 500-word MAIN explanation minimum, six concept pillars, management applications/action/sarabodha, ten-entry batching, one versioned master Word, preservation of 107–112 and full audit requirements. Current user scope controls: no new sutra generation/API calls, no model changes and no manuscript execution before approval. Broader 84 Narada + 100 modern + optional Shandilya scope, Narada-first versus V19-first order, Marathi formula policy and protected closing promises are decisions, not implicit approvals.

Searched the supplied SK_Sutras author-material folder for Udyamasutre_Master_Working_Copy_v1.docx and numbered 107–112 entries. Corresponding working copy not found; a Shandilya 108 citation is not that manuscript. Missing content was not fabricated. Created a proposed primary-topic map covering all 99 substantive candidates plus the separate 100th benediction, with no retention/merge/renumbering applied.

Evidence: logs/author-revision-20261117/Implementation_and_Acceptance_Plan_v2.txt; Master_Prompt_Reconciliation_v2.json; Concept_Allocation_Map_v2.json; working_copy_search.json. Durable user instructions point to v2 as the latest PROPOSED plan. No paid calls, manuscript edits, compilation, commit, push or publication. AWAITING_USER_APPROVAL for book activity.

## 2026-11-17 — Feasible hybrid book plan v3

User requested an informed combination of Options A and B, not execution. Rechecked the 17Nov2026 file inventory and prior working-copy/source evidence. Recommended one consolidated existing-material Udyam book, plus verified Narada source reference 1–84, eleven-Asakti notes and selected verified Shandilya connections in an editable companion section before protected closure. Ancient source items are separately numbered and never counted as new Udyam sutras. No promise of 84 new business adaptations plus 100 additional modern entries.

Full scope, concept coverage, V19 structure, 500-word main exposition requirement, source-specific attribution, verified distinct examples, ten-entry batches, preservation, render QA and author gates are in logs/author-revision-20261117/Hybrid_Implementation_and_Acceptance_Plan_v3.txt. Missing 107–112, complete closing extent and fixed cover/appendix claims remain explicit material decisions. Updated durable instructions to v3 as PROPOSED only.

No manuscript editing/assembly, new generation, API calls, agent/model changes, publication, commit or push. Implementation AWAITS_USER_APPROVAL.


## 2026-11-17 Approved author hybrid consolidation

Scope: existing-source editorial consolidation only; no new sutras, paid provider calls or model changes. OpenSpec: openspec/changes/20261117-author-hybrid-consolidation. Evidence: logs/author-hybrid-book-20261117.

PASS: 104 selected source IDs accounted once in twenty chapters; 84 Narada reference records prepared with explicit variants; first two main expositions 514/517 words; twelve distinct primary-source cases researched for first six entries; internal Word proof preserves opening XML and closing text. NOT_RUN: complete-book editorial/unique-case gates and final all-page visual review. Packaged renderer FAILED because LibreOffice soffice.exe is absent; installed Word COM is the diagnosed fallback. No unrelated app code changed. Offline review is not author approval or publication.


## 2026-11-17 — Approved hybrid consolidation: offline review delivery

Completed 104 existing-source Udyam entries in 20 chapters, with at least 506 Marathi exposition word tokens each (55,486 total), 208 distinct real business cases with public evidence, 84 Narada source items, 11 Asaktis, eight selected verified Shandilya references, and supported reflection/routine appendices. No new Udyam sutras, paid provider calls, credential access, application/model changes, automatic author approval, commit, push or publication. All 13 original source hashes match their baselines.

Loop: content and provenance checks; independent Sanskrit and case audits; 19 recorded Sanskrit/orthographic corrections pending human approval; three example replacements for historical ownership/leadership overlaps; two factual wording repairs; and a complete Word package audit. The first render exposed three short continuation pages, split references and awkward source/bibliography justification. Exposition tightening retained the 500-word minimum; nonbreaking references, left alignment and keeping related source annotations together improved flow. The next render exposed a blank page caused by a standalone page-break paragraph. Moving the break to the following heading changed no text. The final PDF has 253 pages, no empty pages and no text outside page boundaries. Four reviewers individually inspected every final page image. Inherited protected-page sparsity, intentional conclusion/appendix endings and an intact citation wrapping onto its own line are documented accepted layout details.

PASS: full 104/208 coverage; source crosswalk; minimum 506 Marathi words; case identity and repair checks; written Word content matches the reviewed inputs; 20 chapter links and 208 references; all-page visual inspection; exact pixels for the first nine physical pages and protected closing (v2 source page 14); and unchanged originals. The packaged LibreOffice renderer was unavailable because soffice was missing. Microsoft Word COM plus PDFium succeeded as the documented fallback; no packaged-renderer success is claimed.

Delivery: deliverables/20261117-author-hybrid-review contains the Word book, PDF preview, Marathi review notes, source/correction and business-evidence registers, filtration crosswalk, delivery manifest and review ZIP. Detailed proof is in logs/author-hybrid-book-20261117: assembly_manifest.json, final_package_audit.json, final_render_verification.json and the four visual_review_release reports.

Pending human decisions: author/Sanskrit approval, especially N100-013 number and N100-074 lexical choices; protected cover count of 100 versus the actual 104; legacy contents and appendix promises; unsupported validated assessment, complete family constitution and legal/tax appendices. Missing working-copy entries 107–112 were not fabricated. This is a complete review copy, not publication approval or scholarly certification.


## 2026-11-17 — Main sutra centering only

User requested only center alignment of each main Sanskrit formula beneath its entry title. Saved Udyam_Sutre_Hybrid_Review_20261117_Centered.docx alongside the original review book. Exactly 104 paragraph alignment attributes changed; all text, other formatting and other package parts are unchanged. Final render remains 253 pages: 104 formula bands differ, 149 pages are pixel-identical, including the protected opening and closing. All 104 changed pages were individually visually inspected and passed. Evidence: logs/author-hybrid-book-20261117/center-alignment. No content editing, paid APIs or publication.

## 2026-11-18 — Conditional paid reference-grounded edition

User authorized a separate newly generated edition if useful, retaining all five models and exact protected pages. Later steering removes the20/100 hard ceiling and explicitly restricts Claude usage. The current evidence-backed plan has100 entries,20 thematic chapters,200 immutable existing real-business cases and40 assigned source passages; requested-but-unconsulted sources are distinguished. The existing104-entry author consolidation remains unchanged.

Sense: old council genuinely had four discussion voices and a separate validator, but its runner was limited to20, used narrow registered retrieval and the older exporter had unsuitable preservation boundaries. Historical paid outputs were not proof of a100-entry pipeline. Implemented new scoped research council, acceptance, exporter, preparation/paid-run scripts and a Claude-specific durable spending guard. Shared discussions cover up to5related entries; the planned100 entries require292 base Claude calls rather than900, before bounded repairs. SDK network retries remain disabled, callback hard failures stop, and one substantive repair is allowed. Local formatting, source preparation and structural checks use no paid provider.

Verify:103 final council tests passed locally;42 runner/batch/guard tests passed; exporter25 tests and fixture pixel fidelity passed. Source-plan check passed100entries/200cases/839forbidden strings. These are scoped checks, not a full-repository or publication certification.

Paid pilot1 PASS: allfive original roles/models,18calls, no repair,3-word/30-character newformula,672 Devanagari exposition words, independentPASS and structuralPASS. Reservations$0.861013combined/$0.524812Claude; reported-token estimate approximately$0.550344combined/$0.418670Claude, not provider invoices. Evidence under logs/author-research-generation-20261118. Paid phase2 is evaluating the next5entries with shared discussion and a$3.50cumulativeClaude reservation cap. Pilot checkpoint replay made zero additional calls. Actualpilot DOCX is under visual QA; full-book scaling remains conditional on quality and cost. Author approval/publication remain pending.


### 2026-11-18 — Quality stop after nine attempted candidates

Shared-pilot completion and the next discussion batch were followed by two consecutive review holds. The run stopped at9 with six accepted automated drafts (1,2,3,4,6,7);5,8,9 remain held. Independent local reviews found that the semantic ban on the mixed classical/author exclusion ledger conflicted with attributed business reinterpretation. Corrected that instruction, retained exact-copy and within-book material-duplication checks, and added a single explicitly whitelisted independent policy-correction stage.172 scoped offline tests passed before the three GPT-4o reassessments. Those reassessments still held all three drafts; no Claude work was replayed and the quality stop was not bypassed.

Reflection: the system can produce individually useful drafts but has not demonstrated reliable100-entry production. Novelty judgements and short-form meaning need evidence-labelled calibration; concrete grammar/factual qualifications are separately recorded as editorial overlays. No automatic author approval, no model replacement, no completion-count padding and no publication. Current task ends in a six-entry partial review copy, preserving the protected opening and closing, not a complete business journey.

Recorded totals:85 calls,40Claude; reservations$6.526232combined/$4.035906Claude; reported-token estimates$4.55775425combined/$3.393444Claude, not invoices. No paid process remains active. Final Word QA and scoped packaging evidence follow separately.

Final six-entry checkpoint QA PASS:38pages individually inspected,20/20protected-page pixel comparisons passed at two scales; six main formulas centered and12 distinct real-business case records preserved.76 export/audit/editorial tests passed. Original104-entry consolidation and both template hashes unchanged. Delivery manifest and final usage evidence saved under logs/author-research-generation-20261118. This remains a partial review copy, not a complete100-sutra book; author/scholar decisions and NEW007 thematic-overlap review remain pending. Standalone packaging/commit deferred with explicit dependency inventory; no unrelated staged work included, no push or publication.

### 2026-11-18 — Approved validator calibration loop

User authorized narrow reliability changes, offline verification, then small validator calibration; Claude/full generation is conditional on resolution. Implemented independent evidence-only v2 review, explicit categories and substantiation, deterministic objection checks, content/source/rubric-bound cache, corrected-draft checkpoints and export bindings. All five roles and model assignments preserved. Original manuscripts and protected pages untouched.

First calibration FAIL after8GPT-4o calls,$0.364395reserved,0Claude. False uncertainty held good drafts, attribution and case mutations escaped detection, and a mechanical word-count claim contradicted current text. The invalid response stopped without writer repair. Diagnosed v2.2 exposes paired claim/source and case/canonical evidence plus computed counts and permits only concrete quoted uncertainty. Frozen expected labels and texts are unchanged. Follow-up projected$0.4917975; total under original$1. Added cumulative accounting and a cross-process execution lock; no blind replay or retry-to-PASS. Production requires all10frozen probes to pass under the exact implementation and source hashes.187affected and13provenance offline tests passed; final lock/gate checks and live follow-up pending. Full generation remains blocked until that result.

Final verification:391offline tests PASS, including the expanded30case calibration/gate/lock suite and174council/repair/budget regressions. Follow-up v2.2 FAIL after1GPT-4o call,$0.0482525reserved. The response still treated explicitly qualified modern analogies as uncertainty and used an invalid SOURCE_DISTORTION uncertainty category. The strict guard stopped immediately;9remaining probes NOT_RUN. Combined calibration9calls,$0.4126475reserved,$0.1481525reported-token estimate, not invoice;0Claude. No approved calibration exists, so full generation remains BLOCKED under the user's condition. No paid process continues. Original author book, prior six-entry review, V19opening and closing hashes unchanged. Evidence: validator_reliability_final_evidence.json under the research work directory. Failed semantic calibration is not resolved by passing orchestration tests; no automatic PASS or weakened gate. Local implementation retained with packaging/commit limitation unchanged.

### 2026-11-18 — Targeted analogy/false-attribution loop v2.3–v2.4

User authorized the targeted correction, offline tests and small calibration while preserving all models and withholding Claude/full generation until PASS. Added explicit source relationship classification, current comparison/source identity binding, matched rejection evidence, qualified-analogy handling and false-disclaimer controls. Frozen ten-case records/expected labels unchanged; earlier fixture versions archived. Initial273offline tests passed, followed by scoped consistency fixes.

v2.3 live: four legitimate positive controls PASS; exact-copy control missed; false-attribution control correctly rejected semantically but omitted a duplicate explanatory field. OverallFAIL after6calls. v2.4 removed redundant explanation fields while retaining mandatory issue.reason and literal canonical evidence, added mandatory objective violation coverage, and passed339offline tests before inference. Initial v2.4 control005 correctly rejected copying but used the field alias formula. Implemented narrow objective alias normalization with full formula equality and full comparator/predicate validation; preserved rawFAILED evidence and recorded an explicit zero-call recovery. Four positive reviews replayed unchanged. Final369testsPASS in21.59s and33focused recovery assertionsPASS.

Resumed v2.4 firstfive controlsPASS, but control006 again correctly classified false attribution while placing a paraphrase into its literal draft-quote field. Stopped rather than reconstructing that evidence. Controls007–010NOT_RUN; full calibrationFAIL, no approved record, no Claude or full generation. The targeted semantic distinction improved; reliable literal evidence serialization remains unresolved. Next engineering direction: select immutable evidence references and materialize quotations from supplied text, preserving independent semantic decisions and unchanged controls.

Automatic review rejected a generalized$2budget change; the accepted replacement permits only v23/v24 under a combined$1new-round ceiling with the exact historical nine-call/$0.4126475baseline verified. Actual new-round12GPT-4o calls,$0.6303825reserved,$0.296985reported-token estimate (not invoice),0Claude. Allphase106calls/$7.569262reserved. All original book/template hashes unchanged; no paid process remains active. Evidence: logs/author-research-generation-20261118/analogy_validator_final_evidence.json and linked reports/cache records. No author approval, publication or unrelated staged commit.

### 2026-11-18 — Evidence-reference selection v2.5

User explicitly authorized existing-evidence selection, offline tests and one small calibration, preserving all five models and withholding Claude/full generation until PASS. Added typed content-bound draft/source/case IDs, comparison menus and deterministic quotation retrieval. The model retains all semantic judgments; code rejects unknown/stale/cross-owner references and quotes generated outside the selector format. Production calibration binds both reviewer and resolver implementation hashes. The same ten fixture records/labels remain unchanged.

Offline442tests initiallyPASS. Live controls001–006PASS, including the previously blocked false-attribution case. Control007 correctly identified an invented business fact but selected its owner and canonical ID in two fields. Added strictly verified two-ID compatibility, explicit immutable recovery with zero API calls and originalFAILED evidence preserved. Closed an empty recovery-record bypass found during audit. Final476testsPASS in25.22s; targeted recovery audit14/14PASS. Completed model calls total10, including zero-cost replay of completed responses.

Final calibration9/10PASS, overallFAIL: control010 returned READY despite identical business summary/action under a different formula. This is a semantic duplicate-decision miss; all responses now materialize valid existing evidence. Expected labels were not changed and no PASS was forced. Production gate remainsBLOCKED with no approved record;0Claude/full-generation calls, no new manuscript or publication. Next scoped work is explicit per-chapter decision/action comparison, retaining positive distinct-decision controls.

v25reservation$0.6623475underfixed$1; reported-token estimate$0.3713475, not invoice. Historical calibration baseline21calls/$1.04303 retained. Allphase116calls/$8.2316095reserved. All original document hashes and model assignments unchanged. No paid process active. Evidence: logs/author-research-generation-20261118/evidence_reference_validator_final_evidence.json and validator-calibration-v25-report.json. Local packaging/commit limitation from pre-existing mixed index/dependencies remains; no unrelated changes staged or pushed.

### 2026-11-18 — Decision/action comparison v2.6: all ten controls PASS

User authorized comparing each chapter's business decision and action, offline tests and small calibration, preserving all five models and prohibiting Claude/full generation before ten passes. Added paired evidence and mandatory compact judgments covering every supplied prior chapter. Exact copies and identical decisions/actions must have matching blockers; distinct business decisions may share philosophical vocabulary. No missing judgments are filled and no failed label is changed.

Pre-call524offline testsPASS. Firstsix live controlsPASS. Seventh correctly rejected an invented case fact but used its unique supplied business-case ID instead of the internal evidence hash. Added a narrowly typed unique-owner lookup, full ownership/grounding validation and explicit immutable recovery; originalFAILED response preserved. Final affected suites:445testsPASS in19.57s and110integration/export/audit/runner testsPASS in6.13s (555unique, exit0). Focused audits33decision probes and23case/recovery probesPASS. Resumed exact same run: firstsix cache replays, seventh zero-call recovery, only finalthree paid calls.

Final10/10PASS. Different wording with identical business decision/action is rejected as DUPLICATE_DECISION; the nearby but genuinely distinct decision remains READY. Positive analogies and all planted negative controls retain their unchanged expected results. Production gate accepts exact current implementation/input hashes without provider access. Calibration clears this technical blocker, not scholarly certification or a guarantee for every future chapter.

Round10GPT-4o calls,$0.6941925reserved under$1; reported-token estimate$0.4003825, invoice unknown. Allphase126calls/$8.925802reserved. ZeroClaude/full-generation calls this phase; no paid process active. All models and protected manuscript/template hashes unchanged. Technical approval artifact is distinct from author approval, which remainsPENDING. Evidence: logs/author-research-generation-20261118/duplicate_decision_validator_final_evidence.json and validator-calibration-v26-report.json. No publication or unrelated staged commit; existing local packaging limitation remains.


### 2026-11-18 — Authorized full-book-v26 resume; final results pending

Authorization/checkpoint recorded 2026-11-18T19:30:22+05:30. The user authorizes the 100-entry working-target resume after v2.6 calibration; the parent reports `full-book-v26` is running with a $50.891999 run cap and $35 cumulative Claude reservation cap. Historical reservation consumption remains durable. The five existing model assignments and fail-stop quality/provider/budget controls remain unchanged. Earlier entries saying production was stopped or calibration-only are retained as historical checkpoints.

Observed evidence boundary: the parent reports saved entries 001–008 now PASS. This note records that report; this sidecar neither independently inspected the live process nor invoked an API. Full-book completion, remaining-entry outcomes, final spend and final document QA are not yet known. Technical PASS is not semantic-originality certification or author/scholar approval; unresolved editorial judgment remains explicit.

Next validation: reconcile final saved/held checkpoints and exact review bindings; verify canonical source and case fidelity, case-ID reuse, short-form/500-word constraints, Marathi-only prose, material decision/action overlap and significant grammar/factual qualifications. Reconcile calls/tokens/reservations including failures, then render and inspect the final V19 review artifact with protected first-nine/closing and source/template checks. Reservations and reported-token estimates remain distinct from invoices.

Final results PENDING. Parent owns generation control, final accounting, export QA and final evidence updates. This sidecar action appends only proposal/tasks/LOOP documentation; no API call, generation restart, budget change, raw-draft/ledger/code edit, publication or author approval.


### 2026-11-18 — Entry-020 decision-check recovery and same-run resume

Recorded 2026-11-18T19:55:01+05:30; execution and test results below are reported by the parent, not independently rerun by this documentation sidecar. Production stopped at entry 020 because the raw independent review omitted 18 of its 19 required decision checks. The original FAILED response and its audit remain preserved; the decision-coverage requirement was not relaxed.

Added an explicit, one-attempt complete GPT-4o re-review with all existing checks retained. Parent reports 555 existing tests plus 27 new tests PASS. The same ten frozen calibration controls all PASS through cached replay using retained pre_v2 provenance; the replay callback forbids API access. Calibration is bound to the current implementation. These cached results are not ten new live model observations.

One paid GPT-4o recovery then returned entry 020 READY with all 19 decision checks. Reported reservation increment: approximately $0.0922225 ($5.71991675 minus $5.62769425); zero Claude calls for this recovery. Reservation consumption is not an invoice. The same `full-book-v26` run resumed entries 001–020 from cache without new paid calls for those entries; entry 021 composition is ongoing at this checkpoint.

Phase-final results remain PENDING. The parent retains run control and will record the final completed/held set, accounting and artifact QA. This recovery does not grant automatic author/scholar approval, certify all future chapters, or establish completion of the 100-entry target.


### 2026-11-18 — Entry-022 truncated composition; bounded continuation preparation

Recorded 2026-11-18T20:03:54+05:30; this checkpoint records the parent's reported execution/test evidence. Twenty-one chapters PASS. Production stopped at entry 022 when the Sutrakar response reached its 14,000-token maximum at high effort. The saved partial response contains six complete fields: title, formula, grammar, translation, exposition (reported 601 words), and references. No final entry-022 draft has been accepted. The raw HARDFAILED attempt and partial response remain preserved.

Preparation is underway for one explicit continuation using the same Sonnet model, a 6,000-token ceiling and medium effort, requesting only the seven missing fields while preserving the six recovered fields exactly. Continuation-helper tests are PENDING. This is preparation, not evidence that the continuation has run, passed validation or produced an accepted draft.

For future full compositions, the parent reports increasing the output ceiling from 14,000 to 18,000 tokens while keeping high effort and the same model. Seventy-four runner/effort/spend/narrow-repair tests PASS in 3.36 seconds. The reported additional reservation is $0.04 per full composition call; existing budget caps remain unchanged. These passing tests do not cover the still-pending continuation-helper checks.

Reported accounting at this checkpoint: current resume 82 calls / $7.4282205 reserved; all phases 208 calls / $16.3540225 reserved; cumulative Claude reservations $8.33924. Reservations are not invoices. No API process is currently running. Final-book results remain PENDING; the parent owns any subsequent execution, acceptance checks, accounting and final artifact QA.


### 2026-11-18 — Entry-025 local exposition repair; fresh review pending

Recorded 2026-11-18T20:24:59+05:30; parent-reported checkpoint. Generation is paused with 24 entries PASS. Entry 025 has an actual 499-word exposition shortfall; the validator also selected example 0 incorrectly for decision evidence. Neither defect is represented as a passing review.

The parent prepared a 43-word Marathi safe-practice paragraph in `editorial_exposition_additions.json`, bound to the exact seed. No formula or example changes are included. Council `editorial_additions` handling and the runner loader skip already-amended saved seeds, apply the addition once, and retain `local_editorial` provenance with zero provider calls for the local addition. A fresh independent review is mandatory; local word-count repair does not supply or override that review.

Ten focused tests PASS, including the three-resume regression for single application. The broader 197-test run is ONGOING; its result is not yet claimed. The independent-review implementation is unchanged, so the parent reports its existing calibration remains valid. No further Claude call is part of this repair checkpoint.

Generation remains PAUSED at 24 PASS. Fresh independent review, subsequent generation and final-book results are PENDING. The parent retains execution and finalization ownership; this documentation update neither resumes the run nor grants author approval.


### 2026-11-18 — Entries 024–025 comparison-coverage recovery; same-run resume

Recorded 2026-11-18T20:26:38+05:30; parent-reported execution and test results. Entry 025's fresh review of the amended 542-word exposition returned READY but omitted a required comparison. That incomplete response did not satisfy all checks. The existing one-attempt GPT recovery identified by the supplied prefix `ddd7a540...` subsequently passed all checks. No additional Claude call was used for the entry-025 editorial addition.

The parent also reports successful prior comparison-coverage recovery for entry 024, identified by the supplied prefix `369ad883...`. These identifiers are recorded as supplied prefixes, not invented complete hashes. Recovery results remain distinct from the original incomplete responses; missing coverage was not waived or silently filled.

Updated verification: 198 integration tests PASS in 75.22 seconds, plus 10 focused tests PASS. This supersedes the earlier checkpoint's ongoing broader-test status. The same `full-book-v26` run has resumed, with a reported reservation checkpoint of approximately $8.9405. Reservations are not invoices, and this rounded checkpoint is not a final accounting total.

Final generation results, final accounting and final-book QA remain PENDING. The parent retains run control and finalization. This sidecar updates documentation only; no code, provider call, budget change or author approval.


### 2026-11-18 — Entry-026 PASS; typed-archive loader fix and batch 027–031 discussion

Recorded 2026-11-18T20:32:35+05:30; facts reported by the parent. Current checkpoint: 26 entries PASS, no exclusions. Entry 026's comparison-coverage omission was recovered through one GPT review identified by the supplied prefix `ed051ed7...`, yielding READY. The prefix is retained as supplied; no complete identifier is inferred.

The generic typed-archive entry-024 seed-loading bug was fixed in `load_draft_overrides`: typed archives are skipped while legacy override handling is retained. Reported verification: 38 tests PASS in 5.01 seconds, plus 12 focused tests PASS in 1.63 seconds; the real entry-025 seed-hash check also PASS. These are reported scoped results, not a final book-wide validation.

Entries 001–026 replayed from cache without new paid calls. The same process is running batch 027–031 discussion. Current-run reservation checkpoint is approximately $9.3297; this is a reservation amount, not an invoice or final total. Final generation results, accounting and artifact QA remain PENDING.


### 2026-11-18 — Thirty-five PASS; supervisor stop at entry-036 truncation

Recorded 2026-11-18T20:57:16+05:30; parent-reported checkpoint. Entries 032–035 passed, bringing the saved set to 35 passing entries with no exclusions. Coverage failures for entries 028, 029, 030, 031, 032 and 035 were handled. Entry 035 underwent one content revision before READY.

The supervisor was updated to allow the exact cached-review error only with proof of the original FAILED coverage failure and its hash binding. Reported verification: 22 supervisor tests PASS in 1.93 seconds. Recovery remains limited to one per key, at most 100, under fixed caps and a single process. This is a bounded diagnosed-error path, not permission to retry arbitrary failures.

At entry 036, a provider truncation at the 18,000-token ceiling was not recognized as a recoverable supervisor condition. The supervisor correctly STOPPED without an automatic retry. Preparation is underway for a missing-three-field continuation based on ten complete saved fields. No continuation execution, merged acceptance or entry-036 PASS is claimed here. No API process is currently running.

Final generation results, accounting and artifact QA remain PENDING. The parent retains continuation/run control and finalization; this sidecar records supplied facts only.


### 2026-11-18 — Entry-036 continuation structurally accepted; independent review pending

Recorded 2026-11-18T21:00:50+05:30; parent-reported evidence. Forty-seven continuation tests PASS, including the actual entry-036 preparation. One continuation using the same Sonnet model, a 6,000-token ceiling and medium effort filled the three missing fields. All ten complete saved fields were preserved. The merged entry passes structural assessment; independent review remains PENDING, so no entry-036 final acceptance is claimed.

Evidence is recorded in `logs/author-research-generation-20261118/chapter036-continuation-evidence.json`. This sidecar records the parent's report and evidence path without independently reopening the artifact or running providers.

Reported reservation checkpoint: current run $16.51003525; cumulative Claude $13.449646. Reservations are not invoices or final accounting. The single supervisor has resumed with the current core unchanged and all model assignments retained.

Final generation results, independent-review outcome for entry 036, final accounting and artifact QA remain PENDING. The parent retains execution and finalization ownership.


### 2026-11-18 — External Claude credit stop after 42 PASS; export QA pending

Recorded 2026-11-18T21:15:22+05:30; parent-reported current stop. Forty-two entries PASS. During discussion for batch 043–047, Claude returned an HTTP 400 low-credit error. The current blocker is external provider credit, not a validator rejection. No process is active. The asynchronous user response concerning credits is pending; no credit purchase, funding approval or restart is inferred from that pending response. The 100-entry goal remains UNFINISHED.

Current-run accounting: 218 calls, comprising 101 Claude, 86 OpenAI and 31 Google calls; reservations $20.69834525. All-phase accounting: 344 calls / $29.62414725 reserved. Cumulative Claude reservations are $15.853638, below the unchanged $35 guard. Available provider credit and the local reservation guard are separate constraints; being below the guard does not resolve this credit failure. Reservations are not invoices. Parent usage evidence: `logs/author-research-generation-20261118/full-book-v26-usage-at-credit-stop.json`.

A QA agent is working on the 42-entry export. Export/rendering QA is ONGOING, and no final artifact-quality or delivery claim is made here. Original documents are reported preserved, with final rehash verification PENDING. Author approval remains PENDING and is not supplied by technical PASS or the user's generation authorization.

The current generation stop is recorded, but final delivery/QA results remain PENDING. The parent owns the credit-response follow-up, any authorized resume, final accounting reconciliation and final artifact evidence.


### 2026-11-18 — User supersedes generation target with final 42-entry Word review edition

Recorded 2026-11-18T21:19:54+05:30. Following the explicit pause, the user authorizes only this metadata finalization and intentionally ends generation at 42 entries. The current deliverable is the 42-entry Word review edition with the established closing pages. The former 100-entry generation target is SUPERSEDED for this delivery; it is no longer the active credit-blocked objective. The earlier credit failure and incomplete-100 checkpoints remain historical evidence, not the current completion criterion.

Further generation is DEFERRED until author feedback and a new explicit user go-ahead. No paid calls, API calls, new expenses, model substitutions or code changes are authorized by this scope update. Preserve all five existing model assignments and the established first nine pages and closing. This documentation sidecar does not restart any process.

Final export/Word QA remains PENDING with the export agent. Do not claim final rendering success, verified preservation hashes, artifact delivery or author approval without the parent's final QA evidence. The parent will provide that evidence; this sidecar will wait for the update rather than undertake further work.


### 2026-11-18 — Final 42-entry Word review edition READY / DELIVERED; QA PASS

Recorded 2026-11-18T21:32:37+05:30; final QA evidence supplied by the parent. The intentionally scoped 42-entry Word review edition is READY / DELIVERED. Final QA PASS: 157 pages, all visually covered; 20/20 protected-page pixel checks passed; all 42 formulas and 84 case records unchanged; all orphan headings fixed. This sidecar records the supplied final evidence rather than claiming to have rerun the visual inspection.

Delivered Word review file: `deliverables/20261118-agentic-research/Udyam_Sutre_Agentic_Review_042_20261118_Reviewed.docx`

SHA-256: `2ccd7877111fb58ee23162ff4d3d71b6e9e70704f5d4de891be70ecaa64aee86`

QA receipt: `logs/author-research-generation-20261118/final-v26-qa/checkpoint-042-final-02/delivery-qa.json`

Generation ENDED BY USER at 42 entries. The former 100-entry target was superseded for this delivery; no 100-entry completion is claimed. Further generation remains deferred until author feedback and new explicit user authorization. All five model assignments remain unchanged, and the established opening/closing preservation requirement is supported by the reported protected-page checks.

Author/scholar review and approval remain PENDING. Technical delivery/QA success is not publication approval or blanket certification of interpretation or originality. This finalization updates documentation only: no API calls, expenses, generation restart or code changes.


## 2026-11-20 — Source-first comparison resumed

User approved corrections before exhaustive Narada–Shandilya comparison and Marathi scored PDF. Usage exhaustion interrupted tools and subagents; after the user reported restored usage, read/write commands succeeded and source workers were resumed. No customer LLM API keys or paid generation calls were used.

Authoritative scope: openspec/changes/20261120-source-first-comparison/README.md. Approved rubric saved at logs/20261119-sutra-comparison/approved-scoring-policy.json. Primary: total >=60 and component minima30/12.5/10/7.5. Reserve:50<=total<60 descending, considered only if the primary path yields too few suitable distinct entries, still subject to non-forcing and all later checks. Actual verified eligible source counts determine pair coverage;84x100 is provisional.

Verified: corrected Shandilya working JSON has100 sequential IDs and all required nonempty fields. This is structural verification only. Independent full source/meaning review PENDING. Source audit found72 material same-number discrepancies in author DOCX and97 in repository JSON; originals retained. Narada contextual working corpus PENDING. No pairs semantically assessed, no all-pairs PASS, no completed PDF claimed. Next: finish source review, resolve consequential findings, freeze source hashes, assess one-by-100 calibration, independently check its scores, then exhaustive comparison and PDF.


### Source gate and bounded pilot checkpoint

Both working source files now independently reviewed and hash-bound: Shandilya100 PASS_WITH_EXPLICIT_UNCERTAINTIES; Narada84 PASS_WITH_EXPLICIT_QUALIFICATIONS, zero unresolved material findings. Source counts remain84x100, with contextual qualifications preserved. First Narada2x100 draft saved; local coverage/numeric/source-binding audit observed100unique pairs,98pendingreview and2blocked. This is not accepted semantic calibration. Independent review pending;8300remainingpairs and PDF notrun. No customerpaidAPIs; original4inputs remainhashidentical.


### Pilot delivered and exhaustive comparison in progress

N2x100 calibrationPASS after one S62 wording correction, no scorechanges. Reviewedcopy contains3primary,13reserve,5component-rejected,77belowthreshold,2blocked. Marathi pilotPDF48pages fullyvisuallyinspected; no blankpages/outofpageglyphboxes; original4inputsunchanged. Evidence logs/20261119-sutra-comparison/pilot-delivery-qa.json. The PDFisboundedpilot,notfull8400report. Fourassessorsplus2independentreviewers nowcoverremaining8300pairs; assignmentsinwork-assignments.json. Automatedapprovalbrieflyrejectednextstepusingstale18Novbook-stopcontext; verified20NovuserauthorizationandexistingOpenSpec, resubmittedwithscopeevidence, accepted. Bookgenerationremainsstopped; no paidcustomerLLMAPIcalls.

### 2026-11-20 exhaustive comparison final data gate

- PASS: all 84 Narada x 100 Shandilya combinations assessed and independently reviewed at exact current draft/source hashes; 8,400 unique scalar-ID pairs and no missing pairs.
- Counts: 243 PRIMARY; 758 RESERVE; 211 COMPONENT_REJECTED; 7,091 BELOW_THRESHOLD; 97 BLOCKED. Review completion is not acceptance of every pairing or scholar certification.
- All 13 final revision batches repaired and independently rechecked; 100 changed pairs/23 finding groups resolved. Final 12 qualitative controls passed with explicit uncertainties.
- Final structural sidecar verifies all four original source fingerprints unchanged. Paid provider calls and new business-sutra generation remain zero for this activity.
- Evidence: logs/20261119-sutra-comparison/final-data-audit.json, final-semantic-controls-review.json, assessments/hilbert-revision-closure.json and progress.json. Historical interim progress fields are superseded by the exact-hash final aggregate gate; frozen source records were not rewritten to reconcile progress labels.
- Full report DOCX assembled from all-pairs-reviewed.json (SHA256 cd8b76aa23e34a6e74ac2270c3f35e45cb8771d18b64c2eeb1b35a6ef0f9cdf8). PDF rendering and delivery QA remain pending; no final artifact-delivery PASS claimed yet.

### 2026-11-21 — Source-first research screening complete

The full comparison PDF has been delivered separately after all-page automated checks and20 visually inspected pages; no all-page visual or scholar-certification claim. Evidence: logs/20261119-sutra-comparison/full-comparison-delivery.json and full-pdf-qa-v2/qa-checkpoint.json.

All243 PRIMARY source pairs completed14 researcher batches and independent evidence reviews;124 are SUPPORTED with independentPASS. The758 reserve pairs remain separate and have not entered this paid stage. Two ambiguous saved responses were reconciled locally with explicit independently reviewed system holds: N035-S021 and N007-S064 remainPENDING with emptyselectedevidence; other records and raw modelbytes preserved. No evidence guesses or paid formatting regenerations. Boundary tests178PASS; prior10-case final-validator calibration stillPASS.

The29 provider attempts include14 successfulClaude research calls,14 successful independentOpenAI evidence checks, and one original failedClaude attempt retained in the ledger. Research-only reservation total6.112247USD, not actual invoiced spend. The one timeout-correction allowance is exhausted and must not be reused. All successes are checkpointed.

Every cleared pair is preserved in logs/source-first-generation-20261120/all-research-cleared-candidates.json for Sutrakar consideration. Offline curators' business hypotheses are advisory; they are not final Sutrakar acceptance and must not silently remove researched candidates. Writing-stage integration, exact-case/identity checks, source-first four-voice handoff and independent re-review remain in progress. New business-sutra compositions:0. Existing42-entry book, protected templates and originalsources unchanged; authorapproval/publication remainpending.

### 2026-11-21 — Four-voice source pilot: recorded rejection, semantic loop

Executed source-only selection target1 after1097 offline tests plus13 subtests and exact-code gate. Actual N002-S002 completed16 provider calls (four per existing council role), returned Sutrakar REJECT plus three peer PASS; no composition or fifth-validator calls. New business formulas0. Reservation0.87974625USD, Claude0.508968USD; failed historical reservations retained separately. The first rejection remains immutable, not rewritten to claim progress.

Offline diagnosis: logs/sf-council-20261121/source-council-pilot-semantic-review.json. Some objections are valid, but requiring literal business instructions or identical supplemental definitions and vetoing broad old themes misapplies the intended qualified interpretive method. The strongest bounded peer proposal was not specifically evaluated. No evidence proves N2 must pass, that a model change is required, or that provider transport caused this rejection.

Next scoped correction: clarify source-first qualified application and Sutrakar's constructive/arbitrating duty, preserve literal exclusions without concept veto, retain all124 eligible pairs while choosing one ethical-conduct control for a fresh policy-bound pilot. Jason owns selection code/tests; Maxwell and Hilbert separately finish the current-formula lock for nonlinguistic chapter repairs. Offline tests and independent re-review precede any additional paid call. Existing42-entry book and protected source/template files unchanged. No publication, automatic author approval, commit or push performed in this iteration.

### 2026-11-21 — Method v2 and current-formula boundary verified

Implemented only narrow source-selection method/view-label/optional queue changes and the selected-composition nonlinguistic current-formula lock. V2 preserves all124 source packets and other candidates' relative order while prioritizing N078-S028 for the singleton. Source texts, scores, five model assignments and v1 rejection artifacts unchanged; no new schema or discussion round. Prose-only repairs retain the current formula, including an earlier legitimate linguistic correction; unasked replacements remain in raw audit bytes. Explicit current independent linguistic feedback can still request a separately reviewed formula repair.

Actual combined command: .venv/Scripts/python.exe -B -X utf8 -m pytest union(selection.REQUIRED_TESTS,selected.REQUIRED_TESTS,export) -q -x --tb=short --junitxml=logs/source-first-generation-20261120/source-v2-combined-tests.xml --basetemp=C:/Users/LENOVO/AppData/Local/Temp/sf21v2parent. Exit0,1147tests and13subtests PASS in457.90seconds. Exact code hashes at start and finish match. Current source and composition receipts: source-selection-v2-offline-gate.json and selected-book-v2-offline-gate.json. Independent source policy review86testsPASS and selected-book re-review39testsPASS with SELECTED-01 closed; no unresolved required corrections. Tests are structural, not scholarly or chapter semantic certification.

Real124-packet offline replay and selected control preflightPASS. Started exactly one fresh N078-S028 four-voice live calibration under logs/sf-council2-20261121, existing providers/models, checkpointed calls and durable reservations. No larger source batch or long composition started at this checkpoint. Read actual discussion before advancing; acceptance is not predetermined. No commit, push, publication or author approval.

### 2026-11-21 — Bounded v2 calibration: feedback retained, revision loop missing

The singleton N078-S028 yielded a real short Sutrakar proposal but remainedHOLD (two peersPASS, researcherREVIEW_REQUIRED). Dewey's offline source-content review found meaningful method improvement, some valid ethical/practice concerns and some unjustified reference demands. A subsequent ten-pair calibration reused the singleton without new dispatches for it. V2 now covers11pairs:7REJECTED,4heldSutrakarACCEPT,0case-ready,0newmanuscriptchapters. Calls32; reservation3.42275075USD, Claude1.96502USD, not actualinvoice. Original v1 and research reservations unchanged. Evidence: logs/sf-council2-20261121/report.json and source-v2-pilot-semantic-review.json. All124 candidate/source packets remain available; no fullrun claimed.

Root cause for the current advancement stall: peer feedback has no bounded proposal-revision path in the source-only adapter. Existing downstream composition can consume peer feedback, but the newer capsule/selected gates intentionally require threePASS before entry. Retain these gates; do not silently treat an invalid objection as a PASS. An offline mechanical audit confirms all4heldformulas satisfy2–4words/32characters; one reviewer incorrectly called a three-word formula fivewords. This audit is not Sanskrit grammar or semantic clearance.

Next scoped change is a single-entry saved-proposal revision bridge, owned by Jason and independently reviewed by Hilbert. Reuse all original twelve voice stages, sources and input hashes; one Sutrakar repair plus three fresh peer checks. Derived views retain provenance; originalHOLD files and quoted feedback remain immutable. Three actual freshPASS plusACCEPT still required. No extra model, gate loosening or paidloop. All paid activity paused until this new boundary is tested and reviewed. Existing42book and protected opening/closure/templates unchanged; no commit, push or author/publication approval.


### 2026-11-21 — First source-first reader pilot delivered; full primary council running

Saved-proposal revision passed18new offline tests and independent review; lock-authority race fixed before use. Actual N078-S028 repair used4calls, all3freshpeersPASS; reservation0.2610925USD, Claude0.149582USD. Original HOLD and all12 voice stages retained. First composition passed independent5th review in2calls, but reader QA found author-directed guidelines, caveat repetition and S28 context omission; it remains a diagnostic artifact.

A prompt-only reader correction plus offline Marathi reference labels/multiline-quote alignment passed157affected tests and6final prompt/protocol tests. Writer/case/source/validator models and rubric unchanged. Fresh reader composition passed2calls with0.276451USDreservation. Two transparent local editorial corrections copied the verified S27/S28 contextual clauses and removed an incorrect source word-count claim, preserving Sanskrit formula, sources and case facts. One fresh GPT-only current-draft checkPASS (0.0686225USDreservation; zeroClaude). Canonical final draftSHA fd3794617d0e9cfc4985b64e8c90a6fbc4709c003e22fc8f7cd1e838e6e71621. Independent actual-reader/source reviewPASS; main581Marathiwords.

Delivered one-entry diagnostic Word reader pilot: deliverables/20261121-source-first/Udyam_Sutre_Source_First_Reader_Pilot_001_20261121.docx, SHA65019fa12c20e56740837b598172923749fe46f0372340321e8951c001972dcb. Native Word15pages;20protectedpixelchecksPASS, no outsidepage text, sourceformula centered, all15pages visually covered (6fresh/9exact-protected-pixel reuse). Packaged render_docx attempted but unavailable soffice.exe; existing read-only native Word plus bundled pypdfium2 rendered and verified instead. No dependency installed. Receipt logs/source-first-generation-20261120/first-reader-pilot-delivery-qa.json. Author/publication approvalPENDING; this is NOT a100-entry finishedbook.

Full remaining source council resumed to124 at unchanged provider request bindings, reusing cached11; session74778/currentcontrol source-selection-post-reader-control.json. No source status is forced to reach a quota. Parent final export must use first-chapter-editorial/result-reviewed.json for entry1, not either older pilot draft. Actual case identities Toyota/Takata reserved globally for the new manuscript. Maxwell is preparing a separate OFFLINE batched proposal-revision adapter to reduce Claude repair calls across same-batch HOLDs; all existing source runtime stays frozen while paid council runs. No new model, publication, commit or push.


### 2026-11-21 — Partial Gemini peer review retained; bounded completion under review

Source council stopped after21 completed candidates (15REJECT,6HOLD);66 provider attempts including one INCOMPLETE, reservation8.8675695USD includingClaude5.245752USD. No claim that reservations are invoices. The failed Narada Gemini stage reached MAX_TOKENS; historical thinking-token split was not captured, so reasoning exhaustion is a possible mechanism, not proven measured usage. Original raw response and failure/reservation remain retained.

Independent actual-data checks confirm8 complete review objects22–29, missing30/31, and15 sibling stages cached unchanged. The critical objection to Sanskrit loanword अहवालोऽपूर्णः remains REVIEW_REQUIRED. Recovery requests only missing2 through existing Gemini model with explicitMEDIUM and16384 output-token allowance, separate maximum0.25USDreservation and zeroClaude; no request has run at this checkpoint. Completion requires tested receipt binding and independent review before explicit adoption. Original failed dispatch must never become a claimed full successful API response. Subsequent cache hits reverify partial/completion authority.

One independently reviewed reader chapter and delivered15pageWord pilot remain available; no new author approval, publication, commit or push. Batch HOLD repair code22testsPASS, independent review still pending. Progress checkpoint reconciled to stopped source process instead of stale running counters.


Recovery executed after independent GO and1022offline testsPASS. One Gemini request returned only30/31, reservation0.076299USD, zeroClaude. Verified receipt461bdb7d2379aa9b50ddfd3f46441e97ee27868e7701b78c82fbf9a040694d76 adopted with original8 unchanged. Cached target31 replay used zeroadditionalAPI; sourcecalls66/reservation8.8675695 unchanged.31considered:1eligible,10HOLD,20REJECT. Resumed all124 with originalcaps/models and16384/MEDIUM for future newNarada peer calls. Runtime control source-selection-full-recovered-control.json, session92388. Existing paid reservation plus separate recovery counted once. Read-only preflight required directpreflight because run(live=False,resume=True) intentionally mismatches original live manifest; actual original livebindings/caps exactmatchPASS. Automatic review initially rejected implicitmode preflight; explicitoffline alternative used. No gate/consent bypass.


### 2026-11-21 — Two reviewed reader chapters delivered; no blind paid retries

Windows extended read-only SQLite URI compatibility required a narrow reviewed patch (20focusedtestsPASS plus independent9probe/currentauthority checks). Existing running source session kept its tested imported objects; later processes use the separately sealed current code. No source policy/model/request changes in that compatibility correction.

Source fullrun later stopped after71 completed candidates,148attempts,reservation22.08289325USD includingClaude12.9082USD (not invoices). Current72–81batch has15cachedstages; latest researcher review81 changed literal quote जुळतो toजुळते. All10metadata/proposals valid;1ACCEPT80 with3peerPASS,9REJECT. Preserve both actual researcher attempts (latest72PASS, earlier72REVIEW_REQUIRED). Independently reviewed design permits only an exact shared existing Sanskrit anchor, with allvotes/reasons and originalraw/failure retained; implementation/testing pending. No further paid bulk source run.

Two grouped proposal repairs reused original12voice stages: [3,9,11]4calls,reservation0.4838475USD/Claude0.258432USD,3and11ACCEPT,9HOLD; [13,20]4calls,reservation0.373153USD/Claude0.189054USD,13ACCEPT,20HOLD. No repeated paidrepair for9/20. Reviewed globally disjoint case tasks now1,22,3,11 (8examples/30identitykeys);13draftcaseassignmentUnipart/G4S prepared, notregistered.

Entry22reader/sourceQA found overstatementGita12.2 and offered-but-unselected18.55. Fourguardedlocaledits preserveformula/cases,614words. FreshGPTonly independentPASS1call,reservation0.0662075USD,zeroClaude. Canonicalsecond result second-chapter-editorial/result-reviewed.json, draft089328688a108b8f4358730c8a7d2ea852dc879d2e126b64f47fdf3a00a2d157; independentreaderclosurePASS.

TwochapterWord checkpoint delivered: deliverables/20261121-source-first/Udyam_Sutre_Source_First_Review_Checkpoint_002_20261121_Layout.docx SHA0ade0de99ade810306dafe9976065298e7f8bb63a0c7501b74562df13fa97d2a.18pages,20protectedpixelchecksPASS,nooutofpage text, newpages10–17 reviewedfullsize. Anorphanedcaselabel wasfixed withkeepNext only; alltextunchanged, first85nodesunchanged, onlypages15/16changed andbothrechecked. Originalopening9+closing exactpixels reused. Receiptcheckpoint002-delivery-qa.json. Notfull100book, author/publicationPENDING.

Entry3writerSUCCESS retained; fifth response is genuinelyREVISION_REQUIRED for466words but materializationFAILED because evidence incorrectlyselectsnew_sutra. No existingcoverage/CASE_FACTrecovery applies, no fabricatedPASS. Sixguardedlocaledits correctselectedsupplementscope andclarifyexistingdecision, yielding554words and drafte986f4eb60d3d117e8b8b715297cfe1d87033c067de173d8f8f75812c7f33873; actualfreshfifthNOT_RUN. OriginalFAILED remainsunchanged. Optional verifiededitorial-continuation implementation mustprove actualcurrentdraftCOMPLETEfifthresponse andimmutabletask/source/cases, carry allspendonce, andcannot resetfailures. Allnewpaidactivity paused whilefocusedcode/tests/independentreviewcomplete. Noauthorapproval/publication/commit/push.


### 2026-11-21 — Source81 recovered without paid replay; four current drafts cleared

Anchorimplementation independentGO plus250focusedtestsPASS; exactsharedspan receipt ad34a4c5cc85620475dfc76ca2d1afe4088d3973ba3e92400d00136a9fcb5396 adopted. Cachedtarget81materializedall10usingZEROadditionalmodelcalls; calls148/reservation22.08289325USD/Claude12.9082USD unchanged.81completed2directeligible13HOLD66REJECT.80newleadershipproposalcasefit reviewed Buffer2016/EY2022; taskregistry6entries[1,22,3,11,13,80],12uniqueactualexamples/43identitykeys, authorpending.

Selectededitorialcontinuation passedfull58tests plus independentGO. Thirdcorrected554worddraft freshGPTPASS1call0.06667USDreservation/zeroClaude, canonicalthird-chapter-editorial/result-reviewed.json. Firstforksf-book3 reusedcanonical1/22/3 withactualCOMPLETEreviewproof and dedupedheldlineage1.0270865USD; originalFAILED unchanged. New11writerreturned450wordsdespite18000tokenallowance/output4183/end_turn. Higherprompttarget alone ineffective. Fifthagaincorrectlyrequestedlengthrevisionbutselectednew_sutra evidence, leavingfailedmaterialization; rawresponsesretained.

Fourthguardedlocalcopy adds117worddecisionclarificationand1wordspiritualdestination,568words. FreshunchangedcomponentGPTreviewPASS1call0.067045USDreservation/zeroClaude, draftb527b4f7b0e2e122ff11c5a701f8e563e6a2c42709cbbd900f3fa567a195d0b0; independentreader/sourceclosurePASS. Fourcurrentcanonicalchapterresultsreadyfora futureWordexport, notfour-chapterdeliveredfileyet. Actualremainingrootproblem: deterministicassessmentknowswordshortfallbutstillcallspaidfifthbeforeboundedcompletion. Futureoptionalpre-validatorcount+oneexposition-onlycompletionunderexistingcapsbeingimplemented/tested; original450wordresponsewillnotberegenerated. Newsource82+remainsunstartedwhilefutureexisting-fieldreferenceprojectionandcommitted-onlyhistoryareimplemented/offlinetested. No modelchange, automaticapproval/publication or paidblindretry.


## 2026-11-21 continuation — six current reviewed chapters

Six current results (logical 1,22,3,11,13,80) have exact-current-draft fifth PASS and independent reader/source closure. Candidate80 exercised the bounded word-floor completion branch: 481 to 622 Devanagari exposition words before the fifth review; no automatic repeated completion. Candidate13 had only a mechanically incorrect grammar-count clause omitted, followed by a fresh fifth PASS, no Claude editorial call. Six-entry Word checkpoint exported with unchanged text and opening85 nodes; fresh Word/pixel/all editable-page QA is pending. It is not a completed hundred-entry book and author approval remains pending. Source council stays at81 completed; new evidence-menu/committed-only policy passed337 scoped tests and independent review, with target82–91 only awaiting current gate/control reconciliation. Research243 complete,124 cleared; all8400 pair comparison assessments complete. Prior failed calls/reservations and original rejected/held artifacts remain recorded. Book3 held reservation2.052836USD is scope-specific, not total project invoice.


## 2026-11-21 bounded82–91 calibration — stopped, saved proposal recovery

The current-gated ten-pair calibration reused81 old candidates, completed12 new four-voice discussion stages and made two bounded Sutrakar proposal attempts. It stopped before any source-peer or long-writing call. Source cumulative162 provider attempts,24.22454575USDreserved,Claude14.304364USDreserved; these are reservations, not invoices. The native latestsecondresponse accepts87/88 and rejects82–86/89–91. Earlier91ACCEPT must never be selected instead. Both FAILED council attempts retain null callback output because metadata validation raised before returning; full native successful provider responses/raw bytes are saved independently.

Root cause is an identifier representation mismatch: namespaced research-component IDs were exposed alongside canonical packet reference IDs. Three latest selected IDs have independently proven pair-owned, same-passage/locator/hash translations to existing canonical references. Alias-only translation then exposed a second mechanical blocker: the comma in87formula triggers the unchanged short-formula compound-sentence check. Parent explicitly authorized a transparent one-comma omission, preserving all four Sanskrit words/order and all other text/decisions. Maxwell independent detached-data checks pass unchanged metadata/full proposal gates for exactly these four edits, not semantic acceptance. New proof-bound offline recovery implementation/tests/review are required before inserting the missing proposal stage. No reset, source rewrite, prior-response selection, model substitution or extra Sutrakar API call is authorized for this recovery. All three genuinely fresh peer reviews still remain after recovery. Future-only canonical reference menus for wholly unstarted92+ are being prepared, preserving old82..91request bytes. Paid calls remain paused during this work.

The six-entry31-page Word checkpoint006 is delivered for author review: six current fifthPASS/reader closures,12distinct real source-checked examples,20exact protected-page pixel comparisons and every editable page10–30 visually checked. It is not the completed approximately hundred-entry book. Author/publication approval remains pending.


## 2026-11-21 source91 closure and bounded HOLD calibration

Source82–91 completed with3actual fresh peers after zero-cost exactID/comma adoption:8REJECT/all3peerPASS,2HOLD87/88. Source cumulative165calls,24.74951425USDreserved,Claude14.50313USDreserved. Independent semantic closure distinguishes already-present labels/validshape from realhiring-evidence concerns and unresolvedpositiveN68support. No statuses were flipped.

A separately current-gated/independently reviewed4call HOLD-menu calibration87/88 stoppedafter3calls (.2675915USDreserved,Claude.089348): Sutrakarproposal andNaradaPASS saved, ShandilyaREVIEW_REQUIREDnative omittedseverity. Originalroot/terminal/rawsretained. RemainingResearcherClaude call deliberatelyNOT_RUNbecausebothrowsalreadyblocked; no fakegradingorcaseeligibility. Future-onlydesignGO permits explicitUNREPORTED_BY_MODEL missingness ONLY onblockingRQRissues, withnativeabsence preserved, plusopinion-blindfreshpeercontext. Implementation/tests/reviewpending; oldstrictrootunchanged. Nextplannedactionablecalibration26/27 aftercurrentgates, notblind87/88replay.

Content-coveragegap diagnosed: highscoreN001-S00190 andN072-S07885 were researchUNSUPPORTED for lackofspecificsupplementlibrarysupport. TwoIITKpublicoriginals (BrahmaSutra1.1.1,Gita5.18) are prepared/independentlyretrieved exactlineblocks withprovisionalqualifiedMarathimeanings; original17-recordlibrary/scores/statuses/queues unchanged. Separatetwo-candidate enrichmentresearchpreparationrequestedoffline; no paidcallorrelabeling yet. Six-entry Wordcheckpoint006remainslatestreviewdelivery; approximately100-entryaspirationnotachieved, author/publicationapprovalpending.

## 2026-11-22 — Stop-state handover, offline test isolation and remote checkpoint

User requested committing/pushing accumulated project work and a portable AntiGravity handover. Manuscript generation and paid LLM calls remain stopped; no author approval or publication is implied.

Verification: Gitleaks 8.30.1 scanned the complete staged snapshot (including archives) and five local-only commits. Forty-one generic-key flags were individually classified as hexadecimal SHA-256 `review_key` request identities, with exact-fingerprint evidence retained privately. No unclassified credential finding remains in that scope. No security/deployment certification is claimed.

The initial external-network tripwire incorrectly blocked Windows asyncio socketpair loopback. Corrected only the private verification harness to permit loopback and block external sockets/DNS. Two legacy test modules now use synthetic credential files, a temporary seeded Chroma client/local test embeddings, isolated research writes, a temporary document-copy path, and the existing injected five-role runner. These tests establish contract/retrieval plumbing, not scholarly or semantic quality. Production src/scripts, configured models, native responses and the six-chapter manuscript were not changed by these test fixes.

Results: 208 focused provider/replay/peer tests passed; 11 repaired legacy tests passed. The broader remaining run reached 315 passed and 2 skipped, then stopped on five setup errors sharing one legacy recovery bug: scripts/recover_truncated_composition.py constructs ResearchCouncil via object.__new__ without initializing source_first_selection. Deferred the production-helper fix to avoid invalidating saved implementation bindings during handover. The remainder of that run is NOT_RUN; full regression is not PASS. Initial test research-ledger side effects were preserved privately as a diff and restored to the pre-test index state.

The local branch and origin/main had diverged (five local-only commits, one remote-only architecture-document commit). Preserve accumulated changes on a codex handover branch; do not force-push or represent it as a main-branch release. Keep private keys, databases, logs and portable handover material outside Git. Detailed redacted scanner reports, test XML and portable-transfer inventory are under the user-designated Dropbox handover/antigravity folder. Author approval remains PENDING for all six chapters.
