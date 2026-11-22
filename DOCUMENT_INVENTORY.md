# Document inventory

Scope: documents delivered by the 20 November 2026 source-comparison activity only. Historical book/release inventory has not been audited by this task.

| Artifact | Source and generator | Verification |
| --- | --- | --- |
| [Marathi N2 × 100 pilot PDF](deliverables/20261120-source-comparison/Narada_02_Shandilya_100_Comparison_Marathi.pdf) | [Reviewed scores](logs/20261119-sutra-comparison/pilot-narada002-reviewed.json), reviewed Narada/Shandilya working corpora, [builder](logs/20261119-sutra-comparison/build_report.py), [Word renderer](logs/20261119-sutra-comparison/render_report.ps1) | PASS_FOR_PILOT_REVIEW; 48 pages, all visually inspected. [QA receipt](logs/20261119-sutra-comparison/pilot-delivery-qa.json). This is not the full 8,400-pair report or a new business-sutra book. |

Pilot version: layout v3, delivered 20 November 2026.

- Reviewed-score SHA-256: `cf956ed4aafff680f20d5d4f048691797d4872093587e68426ae61963f0cd345`
- Delivered-PDF SHA-256: `6f2fba78b3cc3212dfc7eff10e5d4b9de76277d18cd63303a7bd0d360cdb0387`
- Builder command: bundled Python `build_report.py --scores pilot-narada002-reviewed.json --out <new report.docx> --scope pilot`. Resolve inputs and runtime from the active change/task record.
- Renderer command: `render_report.ps1 -Docx <new report.docx> -Pdf <new task-local.pdf>`; export read-only, repaginate, inspect every rasterized page, then copy the verified PDF to deliverables.
- Full comparison report: IN_PROGRESS; no completed full deliverable is listed.
