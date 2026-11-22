# Author v19 book generation

Status: 20-sutra local draft generated, but all 19 original new verses fail the
corrected short-sutra gate. A separate chapter-2 repair pilot now passes the
length gate but still requires scholarly review. Do not send the full draft for
author acceptance. Governance baseline: 2026.11.11.1.
This change does not approve a sutra, publish an edition, or supersede the
fifteen-gate release workflow in `../20261114-fifteen-gate-council/README.md`.

## Approved outcome

Produce an offline Word book of at most **20 total Udyam Sutras**. Keep the
author's v19 pages 1–9 exactly as rendered. Retain the authored opening sutra
and use its chapter styling for new sutras 2–20. Begin with the reader entering
business, progress through purpose, team, finance, personal and employee
development, then environment, region and world, and end with a closing sutra
on responsible legacy. The title sequence may be refined within this journey.

## Acceptance criteria

- B-01: Narada, Shandilya, researcher and Sutrakar each state a position,
  challenge all three peers, and reply to the complete challenge round.
  Sutrakar synthesizes; the fifth agent receives the completed draft only as an
  independent validator. Exact configured provider/model assignments remain
  Gemini 3.8 Flash, GPT-4o, Claude Sonnet 5.5, Claude Sonnet 5.5 and GPT-4o.
- B-02: Researcher receives theme-matched, located passages from the registered
  knowledge documents, each tied to the current file SHA-256 and source caution.
  Its position cites at least one retrieved source ID where matches exist.
  Superseded manuscripts and editorial analogies cannot be represented as
  original ancient scripture. Every council role can challenge the research.
- B-03: Every new chapter names the exact chosen Narada and Shandilya sutras,
  explains each source briefly in Marathi, and identifies the newly composed
  Sanskrit Udyam Sutra as an original business application. It includes
  padaccheda, anvaya, nirukta, Marathi translation, derivation, at least 500
  whitespace-delimited Marathi explanation words, practical do's and don'ts,
  reflection and reader action. The new Sanskrit line expresses one aphoristic
  business principle in two to four words and at most 32 Unicode characters
  excluding verse delimiters, matching the author's compact opening examples.
  It cannot be a comma-joined prose sentence. English translation
  is omitted.
- B-03 reader presentation amendment (16 November): show the new sutra,
  plain Marathi meaning and business explanation before a very brief source
  connection. Exclude padaccheda, anvaya, nirukta, AI review history and repeated
  technical caveats from the reading edition. Keep scholarly evidence in the
  saved review record. Examples appear once, followed by practical guidance,
  reflection and a small action. Preserve the author's first nine pages.
- B-04: Each new chapter has at least one sourced positive and one sourced
  cautionary business case. People and businesses cannot repeat across new
  chapters or duplicate identified cases in the authored opening. Any necessary
  author exception remains a separate human decision. Identifiable sources
  require factual verification before release.
- B-05: Chapter numbers are consecutive and stop at 20 total. Chapters 16–20
  turn gradually from customer trust and responsible growth to colleagues,
  environment, region and world; chapter 20 closes the book by returning to
  the opening inquiry and inviting a concrete reader commitment. All generated
  content stays local and labelled DRAFT.
- B-06: The Word exporter preserves the original first 109 paragraph XML
  elements and the author template's page geometry, styles, red labels and
  black prose, including Devanagari chapter numerals. Word-rendered pages 1–9
  must match the original pixel for pixel.
  The new chapter begins after the authored opening and follows its layout.
  Internal DOC IDs and source fingerprints stay in the local audit, while the
  book shows readable Marathi source titles and separate explanation bullets.
- B-07: A deterministic failed chapter is revised before it enters the book.
  The independent validator's remaining concerns are retained beside the exact
  draft for Sanskrit-scholar and author review; they never become automatic
  human approval. No public export or publication occurs in this change.

## Implementation and evidence

`src/orchestration/book_council.py` persists exact stage requests and answers
in ignored local SQLite. `src/orchestration/book_acceptance.py` performs the
deterministic checks. `scripts/run_book_council_v19.py` uses the existing
provider registry and audited dispatcher, registered local source retrieval,
and resumable chapter drafts. `src/doc_export/author_book_v19.py` clones the
author's own paragraph styles. Its output is a local author-review Word file.

The affected offline suite covering book, source handoff, existing council,
dispatcher and live-run wiring passed **41 tests** on 15 November 2026 with
exit 0 after enforcing explicit replies to all three peers and normalizing
direct peer-keyed provider replies. The complete
repository suite ran separately: 126 passed and 8 failed in older credential,
Chroma and hardcoded-path tests; it is not a whole-project PASS. Chapter 2's
source-grounded draft has 750 Marathi explanation words; chapter 3 was revised
from 111 to 72 Sanskrit characters while retaining 746 Marathi words.

The local draft has **20 total sutras**, including the author's unchanged
opening and 19 new chapters. Before the shortness correction, the book audit
reported no deterministic issues because its 80-character limit was too loose.
The author's available v19 examples are 19 and 28 characters; the 19 new verses
range from 49 to 77, with a median of 68. The corrected 32-character,
two-to-four-word gate fails every new chapter. No revised Word book has been
generated and no further paid calls have been made. All 19 new
chapters have independent `REVIEW_REQUIRED` verdicts, retained for author and
Sanskrit-scholar review; notably the closing chapters still carry wording,
source-number, case-verification and practical-guidance questions. The Word
draft renders as 100 pages. Its first 12 pages match the author original pixel
for pixel at 72 DPI, exceeding the required untouched pages 1–9. Contact
sheets covering all 88 generated pages were visually inspected for text fit,
and the closing page was inspected at higher resolution. There are 19 new
Word chapter headings, no internal DOC IDs or source hashes in the reader text,
and no doubled Sanskrit verse delimiters. The earlier chapter-14 reply repair
and Anthropic-credit interruption are retained in the local loop record.

The local call ledger reports 595 cumulative calls and $78.52 in estimated
reservations across book work, including earlier attempts. This is not actual
provider billing. The draft stays offline and must be reworked before human
acceptance review. The council now checks compactness at proposal and
composition stages, stopping long proposals before peer review or full draft
generation. Earlier stored discussions can be reused for a targeted repair,
but the repair has not been executed. The Word exporter also refuses any
chapter whose Sanskrit line fails the compactness gate. The corrected affected
offline suite passed 42 tests after the proposal fixture was updated.

Actual provider billing is unknown. Local audits contain provider usage and
estimated reservations, not invoice amounts. No deployment is in scope.

## Chapter 2 short-sutra pilot, 16 November 2026

The user approved one chapter-2 pilot with a $1 reservation ceiling and review
before any later chapter. `scripts/pilot_short_sutra_v19.py` reused the saved
four-agent discussion, Narada and Shandilya source selection, three peer
reviews, business examples, and the existing model assignments. Only Sutrakar
and the independent validator made new paid calls. The dispatcher recorded four
successful calls and **$0.3624765 estimated reservations**, below the ceiling;
actual billing is unknown. No chapter beyond 2 was run.

The separate pilot candidate's sutra is `एकनिष्ठा विक्षेपहानात्॥`, 22 characters
excluding its verse delimiter and two words. The revised Marathi explanation
has 664 whitespace-delimited words. The seven linked fields changed are the
new sutra, padaccheda, anvaya, nirukta, Marathi translation, derivation, and
main explanation. Source sutras, case examples, do's, don'ts, reflection and
reader action remain identical to the original chapter-2 draft. Deterministic
acceptance is `READY_FOR_SCHOLAR_REVIEW`; the fifth validator still returned
`REVIEW_REQUIRED` with seven concerns. These include originality, the source
of `विक्षेप`, duty-preserving nuance and practical boundaries. One grammatical
concern refers to `एकनिष्ठया`, which is absent from the selected sutra; the
validator's comments need human triage rather than automatic acceptance.

The pilot Word excerpt renders as 16 pages. Its first 12 pages match the author
original pixel for pixel at 72 DPI, and the four new pages were visually
inspected without observed clipping. The original chapter and 20-sutra Word
draft were not replaced; the candidate remains a separate offline DRAFT.
