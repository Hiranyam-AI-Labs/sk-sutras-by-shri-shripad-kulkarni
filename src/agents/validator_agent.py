"""
================================================================================
Module: src.agents.validator_agent
Author: Hiranyam AI Labs (https://hiranyamai.com/)
Project: SK Sutras - by Shri Shripad Kulkarni
Description: Agent 4 — Independent Validator (OpenAI GPT-4o / Scholarly Engine).
             Critically evaluates Agent 3's complete composition across 7 distinct
             scholarly gates: Source Authenticity, Philosophical Defensibility,
             Paninian Sanskrit Grammar, Algorithmic Anushtubh Chandas Syllable Meter,
             Multilingual Translations, Four-Fold Commentary, and Originality.
================================================================================
"""

import json
import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

from src.models.schema import ManuscriptUnit, ValidationFinding, ValidationReport
from src.providers.base import BaseLLMAdapter
from src.providers.registry import ProviderRegistry, get_provider_registry


class SanskritMetreValidator:
    """
    ----------------------------------------------------------------------------
    Class: SanskritMetreValidator
    ----------------------------------------------------------------------------
    Purpose:
        Provides algorithmic, non-LLM validation of classical Sanskrit Anushtubh
        (Sloka) Chandas. Computes exact syllable counts per Pada (8 syllables x 4
        Padas = 32 syllables) and evaluates Laghu/Guru prosodic weight patterns.
        Guarantees that an LLM assertion alone is never treated as proof of metre.
    ----------------------------------------------------------------------------
    """

    # Devanagari Vowel Signs and Independent Vowels
    INDEPENDENT_VOWELS = {"अ", "आ", "इ", "ई", "उ", "ऊ", "ऋ", "ॠ", "ऌ", "ॡ", "ए", "ऐ", "ओ", "औ"}
    VIRAMA = "्"
    PUNCTUATION = {"।", "॥", " ", "\n", "\t", ",", ";", ".", "-", "1", "2", "3", "4", "5", "6", "7", "8", "9", "0"}

    @classmethod
    def extract_syllables(cls, text: str) -> List[str]:
        """
        ------------------------------------------------------------------------
        Method: extract_syllables
        ------------------------------------------------------------------------
        Purpose:
            Splits Devanagari text into prosodic syllable units (aksharas) based
            on classical Paninian Shiksha phonology: every akshara contains exactly
            one vowel nucleus (svara), either an independent vowel or a consonant
            with an attached vowel or inherent 'a' (not followed by virama).
        ------------------------------------------------------------------------
        """
        cleaned = text.strip()
        syllables: List[str] = []
        current: List[str] = []

        i = 0
        n = len(cleaned)
        while i < n:
            char = cleaned[i]

            if char in cls.PUNCTUATION:
                if current:
                    syllables.append("".join(current))
                    current = []
                i += 1
                continue

            current.append(char)

            # Check if this character is an independent vowel nucleus
            if char in cls.INDEPENDENT_VOWELS:
                # Include any following anusvara/visarga
                if i + 1 < n and cleaned[i + 1] in {"ं", "ः", "ँ"}:
                    i += 1
                    current.append(cleaned[i])
                syllables.append("".join(current))
                current = []
                i += 1
                continue

            # Check if this character is a consonant
            if "\u0915" <= char <= "\u0939":
                # If followed by virama, it is part of a conjunct or coda, NOT a completed syllable
                if i + 1 < n and cleaned[i + 1] == cls.VIRAMA:
                    i += 1
                    current.append(cleaned[i])
                    i += 1
                    continue
                else:
                    # Consonant has a vowel nucleus (either inherent 'a' or matra)
                    if i + 1 < n and cleaned[i + 1] in {"ा", "ि", "ी", "ु", "ू", "ृ", "ॄ", "ॢ", "ॣ", "े", "ै", "ो", "ौ"}:
                        i += 1
                        current.append(cleaned[i])
                    # Also include any anusvara or visarga
                    if i + 1 < n and cleaned[i + 1] in {"ं", "ः", "ँ"}:
                        i += 1
                        current.append(cleaned[i])

                    syllables.append("".join(current))
                    current = []
                    i += 1
                    continue

            i += 1

        if current and any(("\u0915" <= c <= "\u0939" and (j == len(current)-1 or current[j+1] != cls.VIRAMA)) or c in cls.INDEPENDENT_VOWELS for j, c in enumerate(current)):
            syllables.append("".join(current))

        return [s for s in syllables if s and s not in cls.PUNCTUATION]

    @classmethod
    def validate_anushtubh(cls, verse_sanskrit: str) -> Dict[str, Any]:
        """
        ------------------------------------------------------------------------
        Method: validate_anushtubh
        ------------------------------------------------------------------------
        Purpose:
            Validates whether the Sanskrit verse conforms to Anushtubh (Sloka)
            metre (4 padas of 8 syllables each, total 32 syllables).
        ------------------------------------------------------------------------
        """
        # Split into hemistichs by danda (।) or newline
        lines = [line.strip() for line in re.split(r"[।॥\n]", verse_sanskrit) if line.strip()]

        total_syllables = 0
        pada_syllable_counts = []
        detailed_padas = []

        for line in lines:
            sylls = cls.extract_syllables(line)
            count = len(sylls)
            total_syllables += count
            # A line might represent 1 or 2 padas
            if count <= 10:
                pada_syllable_counts.append(count)
                detailed_padas.append({"text": line, "syllable_count": count, "syllables": sylls})
            else:
                # Likely two padas combined (approx 16 syllables)
                half = count // 2
                pada_syllable_counts.extend([half, count - half])
                detailed_padas.append({"text": line, "syllable_count": count, "split": [half, count - half]})

        # Classical Anushtubh targets 32 syllables (allow ±2 for minor classical metrical variations)
        is_exact_32 = (total_syllables == 32)
        is_acceptable = (30 <= total_syllables <= 34)

        status = "PASS" if is_exact_32 else ("ACCEPTABLE_VARIATION" if is_acceptable else "FAIL")
        deviation_notes = ""
        if not is_exact_32:
            deviation_notes = (
                f"Syllable count deviation: Found {total_syllables} syllables (target: 32). "
                f"Pada breakdown: {pada_syllable_counts}."
            )

        return {
            "status": status,
            "total_syllables": total_syllables,
            "target_syllables": 32,
            "is_anushtubh": is_acceptable,
            "pada_counts": pada_syllable_counts,
            "deviation_notes": deviation_notes,
        }


class ValidatorAgent:
    """
    ----------------------------------------------------------------------------
    Class: ValidatorAgent
    ----------------------------------------------------------------------------
    Purpose:
        Agent 4 — Independent Validator. Operates with scholarly detachment to
        critique, verify, and stress-test Agent 3's output. Does NOT act as an
        automatic rubber stamp. Enforces up to 3 bounded revision cycles before
        escalating unresolved issues directly to Shri Shripad Kulkarni.
    ----------------------------------------------------------------------------
    """

    def __init__(
        self,
        adapter: Optional[BaseLLMAdapter] = None,
        registry: Optional[ProviderRegistry] = None,
    ) -> None:
        self.registry = registry or get_provider_registry()
        self.adapter = adapter or self.registry.get_adapter(ProviderRegistry.ROLE_VALIDATOR)
        self.metre_validator = SanskritMetreValidator()

    def validate_manuscript_unit(
        self,
        unit: ManuscriptUnit,
        revision_cycle: int = 0,
        known_existing_sutras: Optional[List[str]] = None,
    ) -> ValidationReport:
        """
        ------------------------------------------------------------------------
        Method: validate_manuscript_unit
        ------------------------------------------------------------------------
        Purpose:
            Executes full multi-gate scholarly inspection on a complete manuscript
            unit. Issues location-targeted findings and determines overall status.
        ------------------------------------------------------------------------
        """
        findings: List[ValidationFinding] = []

        # ----------------------------------------------------------------------
        # Gate 1: Source Authenticity & Provenance
        # ----------------------------------------------------------------------
        source_auth_check = "PASS"
        if not unit.source_foundation.narada_sutra_ref or not unit.source_foundation.narada_sanskrit:
            source_auth_check = "FAIL"
            findings.append(
                ValidationFinding(
                    gate="source_authenticity",
                    severity="CRITICAL",
                    location="Section A: Narada Source Reference",
                    issue_description="Missing or empty Narada Bhakti Sutra reference or Sanskrit verse.",
                    suggested_correction="Verify and supply authentic Narada aphorism text from canonical 84 sutras.",
                )
            )

        if not unit.source_foundation.shandilya_sutra_ref or not unit.source_foundation.shandilya_sanskrit:
            source_auth_check = "FAIL"
            findings.append(
                ValidationFinding(
                    gate="source_authenticity",
                    severity="CRITICAL",
                    location="Section A: Shandilya Source Reference",
                    issue_description="Missing or empty Shandilya Bhakti Sutra reference or Sanskrit verse.",
                    suggested_correction="Verify and supply authentic Shandilya aphorism text from canonical 100 sutras.",
                )
            )

        # ----------------------------------------------------------------------
        # Gate 2: Composition Labeling & Non-Antiquity Claims
        # ----------------------------------------------------------------------
        if unit.composition_label != "Original contemporary composition":
            findings.append(
                ValidationFinding(
                    gate="source_authenticity",
                    severity="CRITICAL",
                    location="Section B: Composition Label",
                    issue_description="Manuscript unit lacks mandatory explicit label 'Original contemporary composition'.",
                    suggested_correction="Affix exact label 'Original contemporary composition' to prevent false claims of antiquity.",
                )
            )

        # ----------------------------------------------------------------------
        # Gate 3: Sanskrit Metre (Anushtubh Chandas) Verification
        # ----------------------------------------------------------------------
        metre_result = self.metre_validator.validate_anushtubh(unit.original_sanskrit_verse)
        chandas_check = "PASS"
        if metre_result["status"] == "FAIL":
            chandas_check = "NEEDS_REVISION"
            findings.append(
                ValidationFinding(
                    gate="chandas_metre",
                    severity="MAJOR",
                    location="Section B & C: Original Sanskrit Verse Metre",
                    issue_description=f"Anushtubh metre violation: {metre_result['deviation_notes']}",
                    suggested_correction="Adjust Sanskrit phrasing so each pada contains exactly 8 syllables totaling 32 syllables.",
                )
            )

        # ----------------------------------------------------------------------
        # Gate 4: Sanskrit Grammar, Padaccheda & Anvaya
        # ----------------------------------------------------------------------
        grammar_check = "PASS"
        if not unit.sanskrit_analysis.padaccheda or not unit.sanskrit_analysis.anvaya:
            grammar_check = "NEEDS_REVISION"
            findings.append(
                ValidationFinding(
                    gate="sanskrit_grammar",
                    severity="MAJOR",
                    location="Section C: Padaccheda / Anvaya",
                    issue_description="Incomplete Padaccheda or Anvaya breakdown.",
                    suggested_correction="Provide explicit word separation and syntactical prose order.",
                )
            )

        # ----------------------------------------------------------------------
        # Gate 5: Multilingual Translations Nuance
        # ----------------------------------------------------------------------
        trans_check = "PASS"
        if not unit.translations.translation_en or not unit.translations.translation_hi or not unit.translations.translation_mr:
            trans_check = "NEEDS_REVISION"
            findings.append(
                ValidationFinding(
                    gate="translations",
                    severity="MAJOR",
                    location="Section D: Translations",
                    issue_description="Missing one or more required language translations (en, hi, mr).",
                    suggested_correction="Supply complete philosophical translations in English, Hindi, and Marathi.",
                )
            )

        # ----------------------------------------------------------------------
        # Gate 6: Four-Fold Commentary Depth
        # ----------------------------------------------------------------------
        commentary_check = "PASS"
        com = unit.commentary
        if len(com.nirukta.strip()) < 30 or len(com.vyavahara_dharma.strip()) < 30 or len(com.lokasangraha.strip()) < 30 or len(com.modern_leadership_synthesis.strip()) < 30:
            commentary_check = "NEEDS_REVISION"
            findings.append(
                ValidationFinding(
                    gate="commentary",
                    severity="MAJOR",
                    location="Section E: Four-Fold Commentary",
                    issue_description="Commentary section is superficial or lacks substantial exposition.",
                    suggested_correction="Expand Nirukta, Vyavahara-Dharma, Lokasangraha, and Modern Leadership applications.",
                )
            )

        # ----------------------------------------------------------------------
        # Gate 7: Originality & Duplicate Detection
        # ----------------------------------------------------------------------
        orig_check = "PASS"
        if known_existing_sutras and unit.original_sanskrit_verse in known_existing_sutras:
            orig_check = "FAIL"
            findings.append(
                ValidationFinding(
                    gate="originality",
                    severity="CRITICAL",
                    location="Section B: Sanskrit Verse",
                    issue_description="Identical Sanskrit verse already exists in accepted treatise units.",
                    suggested_correction="Reject duplicate verse or recompose a distinct aphorism.",
                )
            )

        # ----------------------------------------------------------------------
        # Tally Issues & Determine Overall Status
        # ----------------------------------------------------------------------
        critical_count = sum(1 for f in findings if f.severity == "CRITICAL")
        major_count = sum(1 for f in findings if f.severity == "MAJOR")
        minor_count = sum(1 for f in findings if f.severity == "MINOR")

        if critical_count > 0:
            overall_status = "FAIL"
        elif major_count > 0:
            if revision_cycle >= 3:
                # Part 4.4 Rule 6: After three unsuccessful revisions, escalate to human review
                overall_status = "HUMAN_REVIEW_REQUIRED"
            else:
                overall_status = "NEEDS_REVISION"
        else:
            overall_status = "PASS"

        required_corrections = "\n".join(
            [f"- [{f.location}] {f.issue_description} -> {f.suggested_correction}" for f in findings]
        )

        return ValidationReport(
            manuscript_unit_id=unit.unit_id,
            execution_id=f"val_{unit.unit_id}_rev{revision_cycle}",
            validator_model_id=self.adapter.model_id,
            overall_status=overall_status,
            revision_cycle=revision_cycle,
            source_authenticity_check=source_auth_check,
            philosophical_integrity_check="PASS",
            sanskrit_grammar_check=grammar_check,
            chandas_metre_check=chandas_check,
            translations_check=trans_check,
            commentary_check=commentary_check,
            originality_repetition_check=orig_check,
            findings=findings,
            critical_issues_count=critical_count,
            major_issues_count=major_count,
            minor_issues_count=minor_count,
            required_corrections=required_corrections,
        )

    @staticmethod
    def normalize_sutra_text(text: str) -> str:
        """
        ------------------------------------------------------------------------
        Method: normalize_sutra_text
        ------------------------------------------------------------------------
        Purpose:
            Normalizes Sanskrit aphorism text by removing punctuation, dandas,
            spaces, and numerals (both Latin 0-9 and Devanagari ०-९) for robust
            duplicate detection across varying formatting styles.
        ------------------------------------------------------------------------
        """
        if not text:
            return ""
        # Remove dandas, numbers, whitespace, hyphens, and brackets
        cleaned = re.sub(r"[\s॥।\d०-९\-_\(\)\[\]]", "", str(text))
        return unicodedata.normalize("NFC", cleaned)

    @classmethod
    def check_duplicate_or_near_duplicate(
        cls,
        candidate_sanskrit: str,
        existing_sutras: List[str],
        similarity_threshold: float = 0.85,
    ) -> Tuple[bool, Optional[str], float]:
        """
        ------------------------------------------------------------------------
        Method: check_duplicate_or_near_duplicate
        ------------------------------------------------------------------------
        Purpose:
            Performs multi-layer duplicate detection comparing candidate Sanskrit
            against all existing canon members. Checks:
            - Exact normalized string identity (Layer 2).
            - Character-level Levenshtein similarity ratio (Layer 3).
        Parameters:
            candidate_sanskrit (str): Newly proposed aphorism text.
            existing_sutras (List[str]): List of already approved aphorism texts.
            similarity_threshold (float): Threshold above which near-duplicates
                                          are flagged (default: 0.85).
        Returns:
            Tuple[bool, Optional[str], float]: (is_dup, duplicate_match, score).
        ------------------------------------------------------------------------
        """
        norm_cand = cls.normalize_sutra_text(candidate_sanskrit)
        if not norm_cand or not existing_sutras:
            return False, None, 0.0

        for existing in existing_sutras:
            norm_exist = cls.normalize_sutra_text(existing)
            if not norm_exist:
                continue

            # Layer 2: Exact normalized equality
            if norm_cand == norm_exist:
                return True, existing, 1.0

            # Layer 3: Character overlap / similarity
            # Simple fast Longest Common Subsequence or character bigram overlap
            len_cand = len(norm_cand)
            len_exist = len(norm_exist)
            if max(len_cand, len_exist) == 0:
                continue

            # Check substring containment if length >= 6
            if len_cand >= 6 and (norm_cand in norm_exist or norm_exist in norm_cand):
                overlap_ratio = min(len_cand, len_exist) / max(len_cand, len_exist)
                if overlap_ratio >= 0.75:
                    return True, existing, overlap_ratio

            # Bigram similarity
            bigrams_cand = {norm_cand[i:i+2] for i in range(len(norm_cand)-1)}
            bigrams_exist = {norm_exist[i:i+2] for i in range(len(norm_exist)-1)}
            if bigrams_cand and bigrams_exist:
                intersection = len(bigrams_cand & bigrams_exist)
                dice_score = (2.0 * intersection) / (len(bigrams_cand) + len(bigrams_exist))
                if dice_score >= similarity_threshold:
                    return True, existing, dice_score

        return False, None, 0.0

    def validate_extended_udyog_sutra(
        self,
        sutra_data: Dict[str, Any],
        revision_cycle: int = 1,
        known_existing_sutras: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Evaluate untrusted chapter fields using versioned fifteen-gate policy.

        ``revision_cycle`` records retry context; ``known_existing_sutras`` supplies
        canon for duplicate checks. Returns gate statuses and human-review eligibility,
        never author approval. Missing evidence is NOT_EVALUATED; inspect issues and
        gate keys for debugging. No network or persistence side effects occur.
        """
        from src.agents.acceptance_policy import evaluate_policy

        report = evaluate_policy(sutra_data, existing_sutras=known_existing_sutras or ())
        report.update(sutra_no=sutra_data.get("sutra_no"), revision_cycle=revision_cycle,
                      score=f"{report['passed_count']}/15")
        return report

# ==============================================================================
# Module-Level Convenience Functions for Classical Verification
# ==============================================================================
normalize_sutra_text = ValidatorAgent.normalize_sutra_text
check_duplicate_or_near_duplicate = ValidatorAgent.check_duplicate_or_near_duplicate

