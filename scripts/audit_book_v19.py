"""Read-only book-wide audit of local, unapproved author-review drafts."""

import json
import sqlite3
from pathlib import Path

from docx import Document

from src.orchestration.book_acceptance import check_chapter
from src.orchestration.book_council import VOICES, reply_coverage


ROOT = Path(__file__).resolve().parents[1]


def audit_book(work: Path, template: Path, expected_total: int = 20) -> dict:
    """Check consecutive chapters, discussions, identities and Word prefix.

    Inputs are an ignored local run directory, the author v19 Word file, and
    the approved total (2–20). Returns a report without changing files or
    granting approval. Missing drafts or stale Word content become issues;
    inspect chapter JSON and the local stage ledger to diagnose them.
    """
    if not 2 <= expected_total <= 20:
        raise ValueError("Expected total must include the authored first sutra and remain at most 20")
    issues = []
    accepted = []
    present = []
    validator_flags = []
    identities = {"जमशेदजी टाटा", "टाटा", "tata", "नारायण मूर्ती",
                  "इन्फोसिस", "infosys", "पेट्स डॉट कॉम", "pets.com"}
    verses = {"अथातो उद्यमजिज्ञासा"}
    database = work / "book_council.db"
    if not database.is_file():
        raise FileNotFoundError(database)
    with sqlite3.connect(database) as db:
        for number in range(2, expected_total + 1):
            path = work / f"chapter-{number:02d}.json"
            if not path.exists():
                issues.append(f"Chapter {number} draft missing")
                continue
            present.append(number)
            record = json.loads(path.read_text(encoding="utf-8"))
            draft, source = record["draft"], record["sources"]
            report = check_chapter(draft, source, identities, verses)
            if report["issues"]:
                issues.append({"chapter": number, "acceptance": report["issues"]})
            discussion = record.get("discussion", {})
            for stage in ("position", "challenge", "reply"):
                if set(discussion.get(stage, {})) != set(VOICES):
                    issues.append(f"Chapter {number} incomplete {stage} round")
            for voice in VOICES:
                challenge = discussion.get("challenge", {}).get(voice, {}).get("challenges", {})
                if set(challenge) != set(VOICES) - {voice}:
                    issues.append(f"Chapter {number} lacks {voice} three-peer challenge")
                answers = discussion.get("reply", {}).get(voice, {}).get("answers")
                missing = (set(VOICES) - {voice}) - reply_coverage(answers)
                if missing:
                    issues.append(f"Chapter {number} {voice} reply omits peers: {sorted(missing)}")
            if not db.execute("SELECT 1 FROM book_stages WHERE chapter=? AND stage=? AND role=?",
                              (number, "independent_review", "validator")).fetchone():
                issues.append(f"Chapter {number} independent validator missing")
            verdict = record.get("acceptance", {}).get("independent_review", {}).get("verdict")
            if verdict == "REVIEW_REQUIRED":
                validator_flags.append(number)
            elif verdict != "PASS":
                issues.append(f"Chapter {number} invalid validator verdict")
            if report["status"] == "READY_FOR_SCHOLAR_REVIEW":
                accepted.append(number)
            verses.add(str(draft.get("new_sutra", "")).strip())
            for example in draft.get("examples", []):
                if isinstance(example, dict):
                    identities.update(str(example.get(key, "")) for key in ("person", "business"))
    output = work / "Udyam_Sutre_v19_New_Book_DRAFT.docx"
    if not output.exists():
        issues.append("Word draft missing")
    else:
        original, book = Document(template), Document(output)
        if len(book.paragraphs) < 109 or any(original.paragraphs[i]._p.xml != book.paragraphs[i]._p.xml
                                              for i in range(109)):
            issues.append("Author's nine-page prefix XML differs")
        for number in accepted:
            display = str(number).translate(str.maketrans("0123456789", "०१२३४५६७८९"))
            if not any(p.text.startswith(f"उद्यम सूत्र {display} :") for p in book.paragraphs[109:]):
                issues.append(f"Chapter {number} absent from Word draft")
    return {"expected_total": expected_total, "new_chapters_present": len(present),
            "new_chapters_accepted": len(accepted),
            "validator_review_required": validator_flags,
            "issues": issues,
            "status": "READY_FOR_AUTHOR_REVIEW" if not issues and len(accepted) == expected_total - 1
            else "INCOMPLETE_OR_NEEDS_REVISION",
            "human_approval": "NOT_PERFORMED", "publication": "NOT_PERFORMED"}


if __name__ == "__main__":
    print(json.dumps(audit_book(ROOT / "logs/book-v19",
          Path(r"C:/Users/LENOVO/Downloads/Udyam_Sutre_Sampurna_Granth_v19.docx")),
          ensure_ascii=False, indent=2))
