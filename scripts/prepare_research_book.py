"""Prepare offline research briefs and provenance; never call a provider or create DOCX.

Purpose: preserve the approved reader journey and immutable cases while supplying
bounded evidence for new writing. Parameters: --root and optional --check-only.
Returns: exit 0 and JSON counts. Failures: missing/duplicate inputs, bad mappings,
case drift or rights-policy violations abort before output. Debug: exception paths,
input hashes and selection decisions in source_catalog.json identify the input.
"""
from __future__ import annotations
import argparse
import collections
import hashlib
import json
import re
from pathlib import Path

WORK = Path("logs/author-research-generation-20261118")
OLD = Path("logs/author-hybrid-book-20261117")
EXCLUDED = {"CMP011", "CMP023", "CMP024"}
MODERN = {"CMP012": "N100-061", "CMP013": "N100-017", "CMP014": "N100-098"}
REF_KEYS = ("id", "title", "author", "locator", "original_text", "meaning_mr", "url", "tradition")
CASE_KEYS = ("kind", "entity", "text_mr", "url", "source_title")
REMOVED = {
    "S105-030": ("N100-012", "Chapter 6 is overfull; reinvestment overlaps funding future productive capacity. Original cases are not transferred."),
    "N100-074": ("N100-049", "Chapter 10 is overfull; human values in prosperity are retained in the dedicated ethics chapter."),
    "N100-015": ("S105-040", "Chapter 11 is overfull; institutions beyond individuals are retained in the succession chapter."),
    "N100-007": ("N100-038", "Chapter 12 is overfull; trust demonstrated in conduct is retained in customer trust and ethical dealings."),
}
# Deliberate title-level matches, not a mechanical Narada/Shandilya pair.
MATCHES = """
N100-001 015 008
N100-002 001 018
N100-008 019 002
S105-016 009 026
N100-013 008 015
N100-016 009 020
V19-002 001 018
N100-006 008 015
N100-089 003 018
N100-005 010 020
N100-053 003 021
N100-003 002 019
N100-034 001 019
N100-019 001 018
N100-061 012 015
N100-024 007 019
N100-047 009 015
S105-015 027 008
N100-057 007 003
S105-046 008 026
S105-092 009 020
N100-068 027 003
N100-054 008 015
N100-017 013 018
N100-087 003 019
S105-050 003 010
N100-012 010 021
N100-014 010 003
S105-022 010 007
S105-023 010 020
S105-028 010 020
S105-029 009 020
N100-086 002 019
S105-020 027 019
N100-028 007 019
S105-056 008 001
N100-066 002 021
S105-045 009 020
N100-045 027 003
N100-039 001 019
N100-027 002 009
N100-085 007 020
N100-069 009 026
N100-038 002 020
S105-019 001 018
N100-018 002 020
N100-004 009 022
N100-010 006 025
S105-034 006 025
S105-039 001 028
S105-033 006 022
S105-079 008 022
N100-063 004 022
N100-021 006 025
S105-032 001 016
S105-035 008 025
N100-044 002 019
N100-046 009 025
S105-062 008 025
S105-044 009 020
S105-052 007 028
S105-051 002 020
S105-026 010 020
N100-029 027 015
S105-057 027 002
S105-037 008 020
S105-071 003 020
N100-088 008 028
N100-036 027 015
N100-048 008 027
N100-042 001 018
N100-041 007 018
N100-011 007 019
N100-033 003 018
S105-072 001 019
S105-027 008 004
S105-038 004 025
S105-055 004 017
N100-037 003 010
S105-058 001 028
N100-040 009 022
N100-084 009 025
N100-030 010 016
N100-049 002 020
N100-055 003 018
S105-054 004 020
S105-036 008 015
N100-079 001 016
N100-023 010 021
N100-077 005 022
N100-098 014 021
S105-060 002 020
S105-069 009 022
S105-070 001 028
S105-040 006 028
S105-076 008 025
S105-085 001 028
N100-050 010 022
N100-022 002 022
S105-096 005 028
"""
QUESTIONS = {
1: "माझ्या कल्पनेमागील गरज आणि पुढची कृती कशी स्पष्ट करावी?",
2: "अनिश्चिततेत निष्ठा आणि विवेक यांचा समतोल कसा राखावा?",
3: "शिकलेले ज्ञान प्रत्यक्ष कामात उपयोगी पडते आहे हे कसे तपासावे?",
4: "ग्राहकाच्या अनुभवातून कोणते गृहितक तपासून निर्णय घ्यावा?",
5: "या निर्णयापूर्वी कोणता पुरावा आणि जोखमीची कोणती सीमा ठरवावी?",
6: "आजचा खर्च आणि उद्याची आर्थिक क्षमता यांचा मेळ कसा घालावा?",
7: "गुणवत्तेतील उणीव शोधून टिकणारी सुधारणा कशी करावी?",
8: "ग्राहकाला प्रामाणिक आश्वासन देऊन विक्री कशी वाढवावी?",
9: "ग्राहकाचा विश्वास रोजच्या व्यवहारात कसा जपावा?",
10: "माणसांची क्षमता आणि जबाबदारी यांचा योग्य मेळ कसा घालावा?",
11: "नेतृत्वाचा निर्णय, सल्ला आणि उत्तरदायित्व स्पष्ट कसे ठेवावे?",
12: "संबंध आणि प्रक्रिया टिकण्यासाठी कोणती स्पष्ट व्यवस्था हवी?",
13: "ज्ञान किंवा तंत्रज्ञानाचा उपयोग आणि त्याची मर्यादा कशी तपासावी?",
14: "नव्या बदलाला पुरावा, प्रयत्न आणि योग्य वेळेची जोड कशी द्यावी?",
15: "अडचणीच्या वेळी विवेक राखून पुढचे पाऊल कसे ठरवावे?",
16: "विस्तार करताना स्थानिक क्षमता आणि परस्परावलंबन कसे जपावे?",
17: "हितसंबंधांचा ताण असतानाही मूल्ये कृतीत कशी टिकवावी?",
18: "उद्योगाचा समाज आणि पर्यावरणावर होणारा परिणाम कसा सुधारावा?",
19: "पुढील पिढीकडे ज्ञान आणि जबाबदारी सुज्ञपणे कशी सोपवावी?",
20: "मिळालेल्या सहकार्याची जाण ठेवून पुढील प्रवासाला दिशा कशी द्यावी?",
}

def read_json(path: Path, manifest: dict):
    """Read local UTF-8 JSON and record its hash.
    Params: path and mutable manifest. Returns: decoded value. Failures: I/O/JSON
    exceptions include path; debug using the manifest SHA256, never credentials.
    """
    raw = path.read_bytes()
    manifest[str(path)] = hashlib.sha256(raw).hexdigest()
    try:
        return json.loads(raw.decode("utf-8-sig"))
    except (ValueError, UnicodeError) as exc:
        raise ValueError(f"Invalid JSON: {path}: {exc}") from exc

def unique_rows(paths, key, manifest):
    """Load rows without precedence guesses.
    Params: paths, unique key, manifest. Returns: keyed rows. Failures: duplicate
    IDs stop the build. Debug: the exception names the conflicting file and ID.
    """
    result = {}
    for path in sorted(paths):
        for row in read_json(path, manifest):
            identity = row[key] if isinstance(key, str) else tuple(row[k] for k in key)
            if identity in result:
                raise ValueError(f"Duplicate {identity} in {path}")
            result[identity] = row
    return result

def references(root, manifest):
    """Canonicalize only the cleared corpus and inherited devotional evidence.
    Params: root and manifest. Returns: registry, Narada links, Shandilya links,
    all comparative rows. Failures: wrong counts/duplicate IDs. Debug: registry ID.
    """
    comparative = read_json(root / WORK / "comparative_sources.json", manifest)
    cleared = [r for r in comparative if r["id"] not in EXCLUDED]
    if len(cleared) != 25:
        raise ValueError("Expected 25 cleared comparative passages")
    registry = {r["id"]: {k: r[k] for k in REF_KEYS} for r in cleared}
    companion = read_json(root / OLD / "source_companion.json", manifest)
    studies = read_json(root / OLD / "source_studies.json", manifest)
    if len(companion["entries"]) != 84 or len(studies["shandilya_selected"]) != 8:
        raise ValueError("Expected 84 Narada and 8 selected Shandilya passages")
    narada_links, shand_links = collections.defaultdict(list), collections.defaultdict(list)
    for prefix, title, author, rows, links in [
        ("Narada", "Narada Bhakti Sutras", "Traditionally attributed to Narada", companion["entries"], narada_links),
        ("Shandilya", "Shandilya Bhakti Sutras", "Traditionally attributed to Shandilya", studies["shandilya_selected"], shand_links),
    ]:
        for row in rows:
            identity = f"{prefix}{row['number']}"
            if identity in registry:
                raise ValueError(f"Duplicate source {identity}")
            registry[identity] = dict(
                id=identity, title=title, author=author,
                locator=f"Sutra {row['number']}; Gita Press publication 385; inherited checked text",
                original_text=row["sanskrit"], meaning_mr=row["meaning_mr"],
                url=companion["reference_url"], tradition="Indian",
            )
            targets = row.get("business_links", [row.get("business_link_id", "")])
            for target in targets:
                if target:
                    links[target].append(identity)
    return registry, narada_links, shand_links, comparative

def formula_corpus(root, manifest, comparative):
    """Collect author, prior-generated and supplied source strings for exclusion.
    Params: root, manifest, comparative rows. Returns: formulas and provenance.
    Failures: malformed existing files stop; absent optional corpora are recorded.
    Debug: provenance gives JSON pointer and path. No claims of source authenticity.
    """
    fields = {"formula", "formula_original", "original_formula", "new_sutra",
              "original", "sanskrit", "original_text", "sutra_sanskrit", "sanskrit_sutra"}
    provenance = collections.defaultdict(list)
    paths = [
        root / OLD / "selected_entries.json", root / OLD / "source_crosswalk.json",
        root / "logs/author-revision-20261117/author_100_entries.json",
        root / OLD / "source_companion.json", root / OLD / "source_studies.json",
        root / WORK / "comparative_sources.json",
        root / "data/raw/narada_bhakti_sutra.json",
        root / "data/raw/shandilya_bhakti_sutra.json",
        root / "data/knowledge_repository/sources/iks_canonical_corpus.json",
    ]
    paths.extend(sorted((root / "logs").glob("book-v19*/chapter-*.json")))
    optional = []
    def visit(value, path, pointer="$"):
        """Collect exclusion strings recursively.
        Params: value, source path, JSON pointer. Returns: None; updates provenance.
        Failures: malformed caller structure raises naturally. Debug: stored pointer.
        """
        if isinstance(value, dict):
            for key, child in value.items():
                location = f"{pointer}.{key}"
                if key in fields and isinstance(child, str) and child.strip():
                    candidates = [child, *child.splitlines()]
                    # Also block a formula stripped of display numbering/dandas.
                    candidates += [re.sub(r"[०-९0-9॥।\s]+$", "", re.sub(r"^[०-९0-9.\s]+", "", child)).strip()]
                    for text in candidates:
                        if text.strip():
                            record = {"path": str(path.relative_to(root)), "pointer": location}
                            if record not in provenance[text]:
                                provenance[text].append(record)
                visit(child, path, location)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, path, f"{pointer}[{index}]")
    for path in dict.fromkeys(paths):
        if path.exists():
            visit(read_json(path, manifest), path)
        else:
            optional.append(str(path.relative_to(root)))
    # Raw text storage schemes vary; all canonical passages are also explicit.
    for row in comparative:
        for text in [row["original_text"], *row["original_text"].splitlines()]:
            if text.strip():
                provenance[text].append({"path": str(WORK / "comparative_sources.json"), "pointer": row["id"]})
    return sorted(provenance), {"records": dict(sorted(provenance.items())), "optional_missing": optional,
                               "policy": "Prohibition only; inclusion does not verify authenticity or authorize use."}

def make_catalog(registry, used, manifest, removed, forbidden_meta):
    """Build requested scope separately from actual selected evidence.
    Params: registry, selected IDs, hashes, removals, forbidden provenance.
    Returns: catalog object. Failures: none beyond malformed caller data.
    Debug: group statuses and used_reference_ids explain coverage without inflation.
    """
    groups = []
    def group(identity, names, count=None, note=""):
        """Append an explicit requested inventory without consultation claims.
        Params: group ID, names, optional count and note. Returns: None.
        Failures: invalid caller types raise naturally. Debug: group ID and items.
        """
        items = [{"id": f"{identity}-{n:02}", "title": name,
                  "status": "requested_not_consulted", "used_reference_ids": []}
                 for n, name in enumerate(names, 1)]
        groups.append({"id": identity, "requested_count": count or len(names),
                       "note": note, "items": items})
    group("four_vedas", ["Rigveda", "Yajurveda", "Samaveda", "Atharvaveda"], 4,
          "Selected Upanishad passages do not establish consultation of entire Vedas.")
    group("six_vedangas", ["Shiksha", "Kalpa", "Vyakarana", "Nirukta", "Chandas", "Jyotisha"], 6)
    group("six_darshanas", ["Nyaya", "Vaisheshika", "Samkhya", "Yoga", "Purva Mimamsa", "Vedanta"], 6,
          "A selected text is not comprehensive coverage of a philosophical school.")
    group("eighteen_puranas", [
        "Brahma Purana", "Padma Purana", "Vishnu Purana", "Shiva Purana", "Bhagavata Purana",
        "Narada Purana", "Markandeya Purana", "Agni Purana", "Bhavishya Purana",
        "Brahmavaivarta Purana", "Linga Purana", "Varaha Purana", "Skanda Purana",
        "Vamana Purana", "Kurma Purana", "Matsya Purana", "Garuda Purana", "Brahmanda Purana"], 18,
        "Working requested inventory; enumerations vary. Narada Purana is not Narada Bhakti Sutras.")
    group("purana_variants", ["Vayu Purana", "Devi Bhagavata Purana"], 2,
          "Vayu retained as a list variant; Devi Bhagavata is distinct from Bhagavata. Neither is claimed consulted.")
    group("eighteen_smritis", ["Manu Smriti", "Yajnavalkya Smriti", "Vishnu Smriti", "Atri Smriti",
        "Harita Smriti", "Ushanas Smriti", "Angiras Smriti", "Yama Smriti", "Apastamba Smriti",
        "Samvarta Smriti", "Katyayana Smriti", "Brihaspati Smriti", "Parashara Smriti",
        "Vyasa Smriti", "Shankha Smriti", "Likhita Smriti", "Daksha Smriti", "Shatatapa Smriti"], 18,
        "Provisional working enumeration, not a uniquely established eighteen-text canon or an author-approved edition list.")
    group("smriti_variants", ["Gautama Dharmasutra / Smriti tradition", "Vasistha Dharmasutra / Smriti tradition"],
          note="Additional traditions recorded separately; not silently substituted into the working eighteen.")
    group("upanishads", ["108 Upanishads (requested corpus)", "Isha Upanishad", "Taittiriya Upanishad"],
          note="108 is a requested scope, not 108 texts consulted. Only named selected passages are used.")
    group("bhakti_and_other_indian_texts", [
        "Narada Bhakti Sutras", "Shandilya Bhakti Sutras", "Bhagavad Gita", "Gita Rahasya",
        "Yoga Sutras", "Yoga Vasistha", "Valmiki Ramayana", "Mahabharata", "Yaksha Prashna",
        "Bhishma-Yudhishthira dialogues", "Krishna-Arjuna dialogue", "Arthashastra",
        "Chanakya Niti", "Bhartrihari Niti Shataka", "Subhashita collections",
        "Panchatantra", "Hitopadesha", "Kiratarjuniya"])
    group("sant_and_indian_thinkers", [
        "Dnyaneshwari", "Amritanubhava", "Tukaram Abhanga Gatha", "Dasbodh", "Manache Shlok",
        "Other Varkari Sant literature", "Swami Vivekananda writings", "Adi Shankaracharya writings",
        "Kalidasa works", "Shivaji Maharaj historical primary sources",
        "Other Indian rulers, social thinkers and nation-builders"],
        note="Dnyaneshwari research candidates remain excluded pending edition collation.")
    group("comparative_philosophers_scientists", [
        "Aristotle", "Seneca", "Marcus Aurelius", "Epictetus", "Adam Smith", "John Stuart Mill",
        "Francis Bacon", "Confucius", "Herbert A. Simon", "Elinor Ostrom", "Daniel Kahneman"],
        note="Confucius provisional transcription excluded. Named passages, not complete author corpora.")
    title_refs = collections.defaultdict(list)
    for identity in sorted(used):
        title_refs[registry[identity]["title"]].append(identity)
    alias = {"Yoga": "Yoga Sutras", "Krishna-Arjuna dialogue": "Bhagavad Gita"}
    for g in groups:
        for item in g["items"]:
            title = alias.get(item["title"], item["title"])
            ids = title_refs.get(title, [])
            if g["id"] == "comparative_philosophers_scientists":
                ids = [key for key in sorted(used) if title in registry[key]["author"]]
            if ids:
                item["status"] = "selected_passages_used"
                item["used_reference_ids"] = ids
                item["coverage"] = "Only listed passages; not comprehensive consultation."
    return {
        "groups": groups, "references": list(registry.values()), "available_reference_count": len(registry),
        "used_reference_ids": sorted(used), "used_reference_count": len(used),
        "excluded_comparative_ids": sorted(EXCLUDED), "selection_decisions": removed,
        "input_sha256": manifest, "forbidden_provenance": forbidden_meta,
        "rights_policy": {
            "CMP012": {"max_entries": 1, "assigned_source_entry_id": MODERN["CMP012"], "comparison_mr_word_limit_exclusive": 100},
            "CMP013": {"max_entries": 1, "assigned_source_entry_id": MODERN["CMP013"], "comparison_mr_word_limit_exclusive": 100},
            "CMP014": {"max_entries": 1, "assigned_source_entry_id": MODERN["CMP014"], "comparison_mr_word_limit_exclusive": 100},
            "modern_quotes": "Canonical quotations only once in the reference appendix, never again in entry prose. Do not redistribute derived claims to other entries.",
            "CMP001": {"render": "Marathi gloss and source attribution only; suppress English quote", "author_rights_review": True},
            "CMP002": {"render": "Marathi gloss and source attribution only; suppress English quote", "author_rights_review": True},
            "all_comparisons": "Under 100 Marathi words per source. Preserve traditional meaning versus modern analogy.",
        },
        "source_policy": "Registry availability is not a claim that all records were selected, all requested texts were consulted, or all traditions agree.",
    }

SEMANTIC_QUESTIONS = {
    32: "ग्राहकाला मिळणारे मूल्य, स्पष्ट अटी आणि व्यवसायाचा टिकाव यांचा मेळ घालून न्याय्य किंमत कशी ठरवावी?",
    42: "प्रत्यक्ष क्षमतेशी जुळणारे वेळेचे वचन देऊन ते सातत्याने कसे पाळावे आणि विलंब झाल्यास ग्राहकाला कसे कळवावे?",
    51: "प्रत्येक सहकाऱ्याला योग्य मोबदला, मानवी प्रतिष्ठा आणि सुरक्षित कामाची परिस्थिती कशी मिळेल?",
    67: "माहितीचे संरक्षण करण्यासाठी प्रवेश नियंत्रण, स्वतंत्र सुरक्षा स्तर, दुरुस्ती आणि घटना-प्रतिसाद यांची सांगड कशी घालावी?",
    78: "कामाचा भार, नियोजित विश्रांती आणि कामासाठीची प्रत्यक्ष क्षमता यांचा समतोल कसा राखावा?",
    97: "अनुभव आणि महत्त्वाचे ज्ञान पुढील सहकाऱ्यांना समजेल व पुन्हा वापरता येईल अशा साधनांत कसे उतरवावे?",
}
SEMANTIC_THEME_097 = "अनुभव आणि महत्त्वाचे ज्ञान समजण्याजोग्या धड्यांत, मार्गदर्शिकांत व सामायिक साधनांत उतरवून पुढील सहकाऱ्यांना शिकण्यासाठी आणि कामासाठी उपलब्ध करावे."
SEMANTIC_FOCUS = {
    8: "तथ्य पडताळल्यानंतर निर्णय घ्या; प्रश्नांची यादी वाढवत अनिर्णयात राहणे आणि पुराव्याशिवाय विश्वास ठेवणे या दोन्ही मर्यादा स्पष्ट करा.",
    17: "ग्राहकाच्या जगण्याचा पद्धतशीर अभ्यास आणि प्रतिनिधिक माहिती यांवर भर; आरंभिक जिज्ञासा किंवा बाजारातील उणीव शोधण्याची पुनरावृत्ती नको.",
    14: "आधी मिळालेले ज्ञान प्रत्यक्ष उपयोगात उतरवण्यातील जबाबदारी व अंमलबजावणीतील अंतर; काम सुरू करण्याची सामान्य प्रेरणा नको.",
    71: "कल्पना किंवा तंत्रज्ञानातून उत्पादन, पुरवठा आणि मागणीशी जुळणारी व्यावसायिक क्षमता उभारण्याचे टप्पे.",
    12: "व्यक्तीचे कौशल्य अचूक आणि पुन्हा करता येणाऱ्या कामाच्या पद्धतीत उतरवणे; संपूर्ण संस्थेच्या गुणवत्ता धोरणापेक्षा हा वेगळा भर आहे.",
    33: "उत्पादन व सेवेचे स्पष्ट गुणवत्ता निकष आणि त्यांची संस्थात्मक जबाबदारी; एखाद्या दोषाच्या कारणशोधनाची तपशीलवार पुनरावृत्ती नको.",
    34: "आढळलेल्या दोषाचे मूळ कारण शोधून त्याची पुनरावृत्ती रोखणारी सुधारणा आणि परिणामाची पडताळणी.",
    35: "दैनंदिन सतर्कता, धोक्याची सूचना आणि काम थांबवण्याचा अधिकार प्रक्रियेत आणणे.",
    13: "सरावानंतरचा अभिप्राय पुढच्या प्रयत्नात वापरण्याचे छोटे शिकण्याचे चक्र.",
    50: "कर्मचारी प्रशिक्षणातून काम करता येण्यापर्यंतचा प्रवास आणि प्रत्यक्ष कौशल्याची कसोटी.",
    68: "बदलते व्यावसायिक संदर्भ शिकणारे नेतृत्व आणि पुढील नेतृत्वक्षमतेचा विकास.",
    94: "कौशल्य शिकण्याची व सन्मानपूर्ण रोजगारात प्रवेशाची संधी; विद्यमान कर्मचाऱ्यांच्या प्रशिक्षणापेक्षा प्रवेशातील अडथळ्यांवर भर.",
    97: "ज्ञान व्यक्तीपुरते न ठेवता पुढील सहकाऱ्यांना वापरता येणाऱ्या सामायिक साधनांत उपलब्ध करणे; शिकविल्याने शिक्षकाचे आकलन वाढले असा अप्रमाणित दावा नको.",
    19: "बाजारातील संधीची वेळ आणि ती पेलण्याची तयारी यांची जुळवणी.",
    42: "ग्राहकाला दिलेली वेळ, प्रत्यक्ष पूर्तता, विलंबाची पूर्वसूचना आणि पुनर्नियोजन; विक्रीवाढ हा सिद्ध परिणाम मानू नका.",
    72: "ठरवलेल्या कृतीची मालकी, मुदत आणि पूर्ततेचा पुरावा; बाजाराच्या वेळेची सामान्य चर्चा नको.",
    73: "बदलत्या परिस्थितीत पुनरावलोकनाचा योग्य क्षण आणि पुढे जाणे, बदलणे किंवा थांबणे यांचा निर्णय.",
    43: "ग्राहकाची अडचण सोडवण्याचे अधिकार आणि समाधानाची प्रत्यक्ष कसोटी.",
    44: "स्पष्ट हमी, डेटा वापर आणि परताव्याच्या मर्यादांमधून विश्वास जपणे.",
    45: "नेमके आश्वासन ठरवणे, त्याची पूर्तता आणि न जमल्यास मान्य उपाय देणे.",
    46: "दावे, आकडे आणि महत्त्वाच्या मर्यादांची तपासता येणारी सत्य मांडणी.",
    47: "मुख्य व्यावसायिक निर्णयांत सदस्य, ग्राहक, कर्मचारी आणि इतर हितसंबंधितांचे हित विचारात घेणे.",
    90: "स्वतःच्या दैनंदिन कामातून निर्माण होणाऱ्या सामाजिक परिणामांची जबाबदारी; देणगी देणे हे तिचे पर्यायस्थान नाही.",
    98: "सामाजिक उद्देशाला सातत्यपूर्ण उत्पन्न, पुनर्गुंतवणूक आणि उत्तरदायित्वाची आर्थिक रचना जोडणे.",
    99: "स्वतःची व संस्थेची उन्नती सार्वजनिक हिताशी सुसंगत ठेवणे; सामाजिक उद्देशाच्या नावाखाली दिशाभूल टाळणे.",
}
SEMANTIC_SPECIFIC = {
    8: "Biocon's founding/export chronology illustrates a concrete next step, not a documented verification or due-diligence process.",
    9: "WeWork's withdrawn IPO illustrates financing uncertainty, not evidence of psychological attachment or the founders' motives.",
    16: "Patisserie's audit failures concern financial-record reliability. The link to gradual learning/saving is indirect; do not call the failure proof of insufficient incremental learning.",
    26: "Aldi's growth chronology does not establish that prudent capacity planning caused its success.",
    30: "Garmin's dated debt-free status does not prove borrowing is generally undesirable, or demonstrate a particular repayment assessment.",
    42: "FedEx's infrastructure and tracking history do not establish a punctuality rate or prove that those features caused reliable delivery.",
    45: "Timpson's published terms illustrate precise promises and exceptions, not independently measured fulfillment performance.",
    58: "DaimlerChrysler's separation does not prove failed cooperation, misconduct, absent rules or a single cause.",
    59: "Sony Ericsson's restructuring/buyout does not establish missing partnership rules or prove that advance rules would have prevented losses.",
    61: "Seneca CMP007 concerns use of time, not record-retention systems. Taittiriya CMP028 concerns study/teaching; institutional documentation is a qualified modern extension.",
    66: "Mill CMP008 supports discussion and correcting judgment, not intellectual-property protection or a legal right to secrecy. Do not present open inquiry as proof of trade-secret controls.",
    67: "Epictetus CMP003 and Patanjali CMP020 provide limited philosophical/ethical comparisons, not cybersecurity engineering prescriptions or empirical security guarantees.",
    71: "Airbus illustrates that technical achievement still needs sufficient commercial demand. Do not describe it as lack of effort or insufficient engineering capability.",
    90: "Akshaya Patra illustrates organized social-service delivery, not demonstrated social responsibility inside a commercial company's core operations. Marcus CMP005 is personal gratitude, not evidence for operational corporate responsibility.",
    95: "HCL records a leadership transition and prior board participation, not proof that the institution became independent of individuals or that hereditary succession is generally effective.",
    97: "Khan Academy supports accessible, reusable learning materials. Neither case establishes that teaching improved the teacher's understanding. Trump University's settlement is not an admission or judicial finding of wrongdoing.",
}
SEMANTIC_NOBEL = {
    15: "CMP012 / Herbert A. Simon: restrict the comparison to workable or satisfactory choices under decision limits. Do not infer that Berkshire used Simon's method, or claim a return/performance guarantee.",
    24: "CMP013 / Daniel Kahneman: restrict the comparison to evaluation of gains/losses and the stated reference framing. It does not establish engineering safety thresholds, SpaceX procedures or OceanGate's failure mechanism. Do not substitute loss-aversion theory for technical safety evidence.",
    91: "CMP014 / Elinor Ostrom: the passage concerns resource users monitoring forest harvesting. Corporate emissions and biomass reporting are a qualified analogy, not direct validation of Interface's metrics or Drax's reporting. Do not claim these companies adopted her framework.",
}

def apply_semantic_review(entries):
    """Add scoped editorial guidance only to future brief metadata.
    Params: mutable entry list. Returns: None; modifies future metadata in place.
    Failures: unexpected numbering raises ValueError. Debug: NEW-ID and constants.
    Source packets, their hashes, cases, reference IDs and entries 1..6 are untouched.
    """
    for entry in entries:
        number = entry["number"]
        if entry["id"] != f"NEW-{number:03}":
            raise ValueError(f"Unexpected identity in semantic review: {entry['id']}")
        if number <= 6:
            continue
        cautions = [
            "Use the exact supplied case text and its evidential limits. A published policy is a stated practice, not proof of compliance, outcomes or causation. A cautionary case is not proof that neglecting this brief's principle caused the event. Preserve allegation, settlement, finding and self-report distinctions.",
            "Keep the traditional meaning separate from the present-day business analogy. Do not attribute modern operational rules to ancient authors or claim that the businesses followed a cited philosopher. Give each comparison a distinct, relevant purpose; keep it under 100 Marathi words.",
        ]
        if number in SEMANTIC_SPECIFIC:
            cautions.append(SEMANTIC_SPECIFIC[number])
        refs = {ref["id"] for ref in entry["source_packet"]["references"]}
        if refs.intersection({"CMP001", "CMP002"}):
            cautions.append("Ross/Aristotle: render an original Marathi gloss with attribution only; do not print the English translation. Translation rights remain for author review.")
        if number in SEMANTIC_NOBEL:
            cautions.append(SEMANTIC_NOBEL[number])
            cautions.append("Nobel restriction: this modern source is assigned to this entry only. Keep its entire Marathi comparison strictly below 100 words. Do not expand beyond the supplied passage, import additional modern claims, or redistribute its quotation/derived claims to other entries. Print the unchanged canonical quotation once in the reference appendix only, never again in entry prose.")
        else:
            cautions.append("Do not import Nobel CMP012/CMP013/CMP014 quotations or derived claims into this entry; their one-entry assignments are reserved elsewhere.")
        entry["editorial_cautions"] = " ".join(cautions)
        if number in SEMANTIC_QUESTIONS:
            entry["reader_question"] = SEMANTIC_QUESTIONS[number]
        if number == 97:
            entry["theme"] = SEMANTIC_THEME_097
        if number in SEMANTIC_FOCUS:
            entry["distinct_focus"] = SEMANTIC_FOCUS[number]

def semantic_review_proof(before, after, forbidden_bytes, source_catalog_bytes):
    """Validate the requested freeze and construct a before/after audit.
    Params: old/new plan objects and exact protected-file bytes. Returns: proof.
    Failures: any unapproved delta raises ValueError before writes. Debug: entry
    IDs and changed field names; digests use canonical JSON, not Python repr.
    """
    def digest(value):
        """Hash JSON evidence. Params: JSON value. Returns: SHA256 string.
        Failures: non-JSON data raises TypeError. Debug: inspect the caller value.
        """
        return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                        separators=(",", ":")).encode("utf-8")).hexdigest()
    if set(before) != set(after):
        raise ValueError("Unexpected plan top-level keys")
    if len(before["entries"]) != 100 or len(after["entries"]) != 100:
        raise ValueError("Expected 100 briefs for this frozen semantic adjustment")
    for key in before:
        if key != "entries" and before[key] != after[key]:
            raise ValueError(f"Unexpected top-level change: {key}")
    if before["entries"][:6] != after["entries"][:6]:
        raise ValueError("Paid entries NEW-001..NEW-006 changed")
    changes, packet_checks, modern_assignments = [], [], {}
    allowed = {"reader_question", "theme", "editorial_cautions", "distinct_focus"}
    for old, new in zip(before["entries"], after["entries"]):
        number = old["number"]
        if old["id"] != new["id"]:
            raise ValueError("Entry ordering or IDs changed")
        changed = sorted(k for k in set(old) | set(new) if old.get(k) != new.get(k))
        if set(changed) - allowed or (number <= 6 and changed):
            raise ValueError(f"Unapproved changes to {old['id']}: {changed}")
        if "reader_question" in changed and number not in SEMANTIC_QUESTIONS:
            raise ValueError(f"Unapproved reader question change: {old['id']}")
        if "theme" in changed and number != 97:
            raise ValueError(f"Unapproved theme change: {old['id']}")
        if "distinct_focus" in changed and number not in SEMANTIC_FOCUS:
            raise ValueError(f"Unapproved focus change: {old['id']}")
        if old["source_packet"] != new["source_packet"] or old["source_packet_sha256"] != new["source_packet_sha256"]:
            raise ValueError(f"Frozen packet changed: {old['id']}")
        calculated = digest(new["source_packet"])
        if calculated != old["source_packet_sha256"]:
            raise ValueError(f"Stored packet hash mismatch: {old['id']}")
        old_refs = [r["id"] for r in old["source_packet"]["references"]]
        new_refs = [r["id"] for r in new["source_packet"]["references"]]
        if old_refs != new_refs:
            raise ValueError(f"Reference order/IDs changed: {old['id']}")
        for ref in new_refs:
            if ref in MODERN:
                if ref in modern_assignments:
                    raise ValueError(f"Modern source repeated: {ref}")
                modern_assignments[ref] = new["id"]
        if number > 6 and not isinstance(new.get("editorial_cautions"), str):
            raise ValueError(f"Missing editorial caution: {old['id']}")
        if changed:
            changes.append({"id": old["id"], "changed_fields": changed,
                "before": {k: old.get(k) for k in changed},
                "after": {k: new.get(k) for k in changed}})
        packet_checks.append({"id": old["id"], "before_sha256": old["source_packet_sha256"],
                              "after_sha256": new["source_packet_sha256"], "equal": True,
                              "reference_ids": new_refs,
                              "case_ids": [c["case_id"] for c in new["source_packet"]["examples"]]})
    if modern_assignments != {"CMP012": "NEW-015", "CMP013": "NEW-024", "CMP014": "NEW-091"}:
        raise ValueError("Nobel assignments changed")
    return {"status": "PASS", "scope": "Future brief metadata only; no provider calls",
        "protected_entries": {"ids": [e["id"] for e in before["entries"][:6]],
                             "exact_json_equal": True,
                             "before_sha256": digest(before["entries"][:6]),
                             "after_sha256": digest(after["entries"][:6])},
        "all_source_packets_exactly_equal": True, "all_cases_exactly_equal": True,
        "all_reference_ids_and_order_equal": True, "chapter_titles_and_plan_metadata_equal": True,
        "forbidden_file": {"before_sha256": hashlib.sha256(forbidden_bytes).hexdigest(),
                           "after_sha256": hashlib.sha256(forbidden_bytes).hexdigest(),
                           "bytes_unchanged": True},
        "source_catalog": {"before_sha256": hashlib.sha256(source_catalog_bytes).hexdigest(),
                           "after_sha256": hashlib.sha256(source_catalog_bytes).hexdigest(),
                           "bytes_unchanged": True},
        "modern_assignments": modern_assignments, "changed_entry_count": len(changes),
        "reader_question_changes": [f"NEW-{n:03}" for n in sorted(SEMANTIC_QUESTIONS)],
        "theme_changes": ["NEW-097"], "distinct_focus_count": len(SEMANTIC_FOCUS),
        "changes": changes, "packet_checks": packet_checks}

def save_semantic_adjustment(root, after, check_only=False):
    """Snapshot and save the validated metadata-only plan adjustment.
    Params: root, regenerated plan, check-only flag. Returns: audit proof.
    Failures: baseline drift or protected-file drift aborts; I/O errors propagate.
    Debug: snapshot and semantic_review_adjustments.json contain exact old hashes.
    Existing snapshots are never overwritten. No source catalog/forbidden writes.
    """
    output = root / WORK
    path = output / "plan.json"
    snapshot = output / "plan.pre_semantic_review.json"
    audit = output / "semantic_review_adjustments.json"
    old_bytes = path.read_bytes()
    forbidden_path = output / "forbidden_formulas.json"
    catalog_path = output / "source_catalog.json"
    forbidden_bytes, catalog_bytes = forbidden_path.read_bytes(), catalog_path.read_bytes()
    current = json.loads(old_bytes.decode("utf-8"))
    baseline_bytes = snapshot.read_bytes() if snapshot.exists() else old_bytes
    baseline = json.loads(baseline_bytes.decode("utf-8"))
    semantic_review_proof(current, after, forbidden_bytes, catalog_bytes)
    proof = semantic_review_proof(baseline, after, forbidden_bytes, catalog_bytes)
    new_bytes = (json.dumps(after, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    proof.update(snapshot=str(snapshot), plan_before_sha256=hashlib.sha256(baseline_bytes).hexdigest(),
                 plan_after_sha256=hashlib.sha256(new_bytes).hexdigest())
    if check_only:
        return proof
    if path.read_bytes() != old_bytes or forbidden_path.read_bytes() != forbidden_bytes or catalog_path.read_bytes() != catalog_bytes:
        raise ValueError("Inputs changed during semantic preparation; retry when stable")
    if not snapshot.exists():
        with snapshot.open("xb") as handle:
            handle.write(old_bytes)
    if path.read_bytes() != new_bytes:
        path.write_bytes(new_bytes)
    if forbidden_path.read_bytes() != forbidden_bytes or catalog_path.read_bytes() != catalog_bytes:
        raise ValueError("Protected file changed concurrently; inspect audit before proceeding")
    if path.read_bytes() != new_bytes or snapshot.read_bytes() != baseline_bytes:
        raise ValueError("Saved plan/snapshot verification failed")
    audit_bytes = (json.dumps(proof, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if not audit.exists() or audit.read_bytes() != audit_bytes:
        audit.write_bytes(audit_bytes)
    return proof



def build(root: Path):
    """Construct and validate outputs entirely in memory.
    Params: repository root. Returns: plan, catalog, forbidden list. Failures:
    count/schema/case/reference/rights violations raise ValueError. Debug: entry ID.
    """
    manifest = {}
    selected = unique_rows([root / OLD / "selected_entries.json"], "id", manifest)
    editorial = unique_rows((root / OLD).glob("editorial-[0-9]*.json"), "id", manifest)
    cases = unique_rows((root / OLD).glob("cases-[0-9]*.json"), ("entry_id", "kind"), manifest)
    journey = read_json(root / OLD / "reader_journey.json", manifest)["chapters"]
    if len(selected) != 104 or len(journey) != 20 or len(cases) != 208:
        raise ValueError("Expected existing 104 entries, 20 chapters and 208 cases")
    ordered = [identity for chapter in journey for identity in chapter["source_ids"]]
    if len(ordered) != 104 or set(ordered) != set(selected) or set(editorial) != set(selected):
        raise ValueError("Selection/editorial/journey coverage mismatch")
    registry, narada, shand, comparative = references(root, manifest)
    mapping = {}
    for line in MATCHES.strip().splitlines():
        identity, *numbers = line.split()
        if identity in mapping:
            raise ValueError(f"Duplicate reference mapping {identity}")
        mapping[identity] = ["CMP" + number for number in numbers]
    retained = set(selected) - set(REMOVED)
    if set(mapping) != retained:
        raise ValueError(f"Mapping mismatch missing={retained-set(mapping)}, extra={set(mapping)-retained}")
    removals = []
    for identity, (target, reason) in REMOVED.items():
        chapter = next(c for c in journey if identity in c["source_ids"])
        if len(chapter["source_ids"]) <= 5 or chapter["chapter"] in (1, 20) or target not in retained:
            raise ValueError(f"Invalid overlap removal {identity}")
        removals.append({"source_entry_id": identity, "chapter": chapter["chapter"],
                         "title_mr": editorial[identity]["title_mr"], "overlap_retained_id": target,
                         "reason": reason, "cases_transferred": False})
    entries, chapters = [], []
    for chapter in journey:
        chapter_entries = []
        for identity in chapter["source_ids"]:
            if identity in REMOVED:
                continue
            number = len(entries) + 1
            ids = list(mapping[identity])
            # At most one devotional addition, supported by the prior explicit mapping.
            # The pilot deliberately has just one Indian and one Western passage.
            if identity != "N100-001":
                extra = shand.get(identity, []) if identity in ("V19-002", "N100-019") else narada.get(identity, [])
                if extra:
                    ids.append(extra[0])
            packet_cases = []
            for kind in ("positive", "caution"):
                old_case = cases.get((identity, kind))
                if old_case is None or not old_case.get("verification"):
                    raise ValueError(f"Missing verified case {identity}-{kind}")
                packet_cases.append({"case_id": f"{identity}-{kind}", **{k: old_case[k] for k in CASE_KEYS}})
            source_packet = {"references": [dict(registry[key]) for key in ids], "examples": packet_cases}
            title = editorial[identity]["title_mr"]
            question = f"{title}: {QUESTIONS[chapter['chapter']]}"
            if identity == "N100-001":
                question = "मला कोणत्या ग्राहकाची कोणती अडचण समजून घ्यायची आहे आणि माझे गृहितक प्रश्न व चर्चेतून कसे तपासावे?"
            entry = {"id": f"NEW-{number:03}", "number": number, "chapter": chapter["chapter"],
                     "batch_id": chapter["chapter"], "title_mr": title, "reader_question": question,
                     "theme": editorial[identity]["meaning_mr"], "source_entry_id": identity,
                     "source_packet": source_packet}
            entry["source_packet_sha256"] = hashlib.sha256(json.dumps(source_packet, ensure_ascii=False,
                sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
            entries.append(entry)
            chapter_entries.append(entry)
        chapters.append({"chapter": chapter["chapter"], "batch_id": chapter["chapter"],
                         "title": chapter["title"], "title_mr": chapter["title"],
                         "entry_ids": [e["id"] for e in chapter_entries],
                         "source_ids": [e["source_entry_id"] for e in chapter_entries],
                         "count": len(chapter_entries)})
    apply_semantic_review(entries)
    used = {r["id"] for e in entries for r in e["source_packet"]["references"]}
    usage = collections.Counter(r["id"] for e in entries for r in e["source_packet"]["references"])
    if len(entries) != 100 or len({e["id"] for e in entries}) != 100:
        raise ValueError("Working selection should currently contain 100 unique briefs")
    if chapters[0]["source_ids"] != journey[0]["source_ids"] or chapters[-1]["source_ids"] != journey[-1]["source_ids"]:
        raise ValueError("Opening or closing chapter changed")
    if [c["title"] for c in chapters] != [c["title"] for c in journey]:
        raise ValueError("Protected reader-journey chapter title changed")
    for e in entries:
        refs = e["source_packet"]["references"]
        if not 2 <= len(refs) <= 4 or len({r["id"] for r in refs}) != len(refs):
            raise ValueError(f"Bad reference packet {e['id']}")
        for r in refs:
            if r != registry[r["id"]]:
                raise ValueError(f"Noncanonical reference {e['id']}")
        for case in e["source_packet"]["examples"]:
            original = cases[(e["source_entry_id"], case["kind"])]
            if any(case[k] != original[k] for k in CASE_KEYS):
                raise ValueError(f"Immutable case changed: {case['case_id']}")
        for source in MODERN:
            if source in {r["id"] for r in refs} and e["source_entry_id"] != MODERN[source]:
                raise ValueError(f"Modern source assigned to wrong entry: {source}")
    if any(usage[k] > 1 for k in MODERN):
        raise ValueError("Modern source reuse exceeds one entry")
    if {r["tradition"] for r in entries[0]["source_packet"]["references"]} != {"Indian", "Western"}:
        raise ValueError("Pilot needs Indian and Western evidence")
    for r in registry.values():
        if any(not r.get(k) for k in REF_KEYS):
            raise ValueError(f"Incomplete canonical source {r['id']}")
    formulas, forbidden_meta = formula_corpus(root, manifest, comparative)
    for r in registry.values():
        for text in [r["original_text"], *r["original_text"].splitlines()]:
            if text and text not in formulas:
                formulas.append(text)
    formulas.sort()
    catalog = make_catalog(registry, used, manifest, removals, forbidden_meta)
    catalog["reference_entry_usage"] = dict(sorted(usage.items()))
    catalog["packet_hash_algorithm"] = "SHA256 of UTF-8 JSON with ensure_ascii=False, sort_keys=True, separators=(',', ':')"
    catalog["case_count"] = 200
    catalog["forbidden_formula_count"] = len(formulas)
    limitations = [
        "100 is the current working selection, not a user-imposed ceiling; chapter batching does not change entry or case IDs.",
        "All 20 chapter titles and the entire opening/closing chapter sequences are copied unchanged from reader_journey.json. Protected document pages were not opened or modified.",
        "Source pool: 25 cleared comparative passages + inherited 84 Narada + 8 Shandilya = 117 records. source_count counts distinct passages actually assigned.",
        "CMP011, CMP023 and CMP024 are excluded pending facsimile/edition collation; Marathi Sant and Confucius coverage is not claimed.",
        "Narada/Shandilya verification is inherited from the existing source companion, not newly reverified online. Devotional meanings remain devotional; business use is analogy.",
        "Thematic evidence is not operational law: no ancient claim about modern cash flow, cybersecurity, pricing regulations or corporate succession is implied.",
        "Each Nobel source is assigned to at most one entry. Each comparison must be under 100 Marathi words. Print its canonical quote once in the reference appendix only; no duplicate entry quotation or redistributed modern claims.",
        "Ross Aristotle English quotations are research-only. Render original Marathi gloss plus source attribution; author rights review remains pending.",
        "Source catalog requested inventories are not evidence of consultation. The eighteen-Smriti list is provisional and lists vary; Vayu and Devi Bhagavata are separately identified.",
        "All case fields are copied exactly from current cases-*.json; case verification is inherited, not independently repeated in this offline build.",
        "Forbidden strings include original/corrected selected formulas, source crosswalk, author100, available old generated chapter drafts and supplied source lines. Exact-string coverage alone cannot detect semantic paraphrase.",
        "The parent runner controls generation, cost, pilot selection and rendering. This script performs no paid calls, accesses no keys and creates no DOCX.",
        "Pilot NEW-001 may run alone; remaining entries can be grouped by batch_id/chapter without changing source packets or their hashes.",
    ]
    plan = {"entries": entries, "chapters": chapters, "source_count": len(used), "limitations": limitations}
    return plan, catalog, formulas

def main(argv=None):
    """Execute deterministic offline preparation.
    Params: optional argv (--root, --check-only). Returns: 0. Failures propagate
    before writing when validation fails; filesystem errors identify destination.
    Debug: stdout counts and source_catalog input/packet hashes. No runner import.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--semantic-review-only", action="store_true",
                        help="Regenerate future metadata with paid entries and packets frozen; save snapshot/proof only")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    plan, catalog, forbidden = build(root)
    if args.semantic_review_only:
        proof = save_semantic_adjustment(root, plan, args.check_only)
        print(json.dumps({"semantic_review": proof["status"], "changed_entries": proof["changed_entry_count"],
                          "protected_entries_equal": proof["protected_entries"]["exact_json_equal"],
                          "packets_equal": proof["all_source_packets_exactly_equal"]}))
    elif not args.check_only:
        output = root / WORK
        output.mkdir(parents=True, exist_ok=True)
        for name, value in (("plan.json", plan), ("source_catalog.json", catalog), ("forbidden_formulas.json", forbidden)):
            (output / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"entries": len(plan["entries"]), "chapters": len(plan["chapters"]),
        "cases": catalog["case_count"], "available_references": catalog["available_reference_count"],
        "used_references": plan["source_count"], "forbidden_formulas": len(forbidden),
        "modern_usage": {k: catalog["reference_entry_usage"].get(k, 0) for k in MODERN},
        "pilot": plan["entries"][0]["id"], "check_only": args.check_only}, ensure_ascii=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
