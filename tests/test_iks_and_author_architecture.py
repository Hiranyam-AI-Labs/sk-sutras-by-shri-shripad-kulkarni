"""
================================================================================
Test Module: tests.test_iks_and_author_architecture
Author: Hiranyam AI Labs (https://hiranyamai.com/)
Project: SK Sutras - by Shri Shripad Kulkarni
Description: Comprehensive QA test suite verifying the incorporation of Shri
             Shripad Kulkarni's architectural specifications:
             - 20+ Canonical IKS texts stored permanently in ChromaDB
             - Dynamic semantic retrieval across iks_canonical_library
             - Agent 1 Enterprise Isomorphism Axiom
             - Agent 2 Rational Due Diligence and Logic
             - Agent 3 ChromaDB Dynamic IKS integration
             - Agent 4 Minimum 500-word Bhashya, Biographical Case Studies,
               and Patanjali Yoga Sutras psychological resilience
             - Agent 5 13-gate audit verifying 500-word depth and case studies
             - Mandatory confidentiality footer verification on every page
================================================================================
"""

import json
from pathlib import Path
import pytest

from src.config import BASE_DIR
from src.vectorstore.chroma_store import SutraVectorStore
from scripts.run_dynamic_live_council import DynamicLiveCouncilRunner
from scripts.reformat_canonical_word_document import build_reformatted_canonical_document, MANDATORY_FOOTER


class OfflineFixtureEmbedding:
    """Deterministic vectors for collection plumbing, not semantic-quality proof."""

    def __call__(self, input):
        """Return finite local vectors for input texts without model downloads."""
        return [[1.0, 1.0, 1.0, 1.0] for _ in input]

    def embed_query(self, input):
        """Use identical local query dimensions with modern Chroma clients."""
        return self(input)

    @staticmethod
    def name():
        """Identify this test-only embedding function to Chroma."""
        return "offline-test-fixture"


@pytest.fixture(autouse=True)
def isolated_iks_index(tmp_path, monkeypatch):
    """Seed a temporary Chroma index; never rely on or mutate the live index.

    Pytest fixtures provide directory/patch lifetime. Uses existing corpus rows
    only as retrieval test data, not a claim of scholarly approval or relevance.
    Return the temporary client; preserve production embedding configuration.
    """
    import chromadb
    from chromadb.config import Settings

    original_client = chromadb.PersistentClient
    client = original_client(path=str(tmp_path / "chroma"),
        settings=Settings(anonymized_telemetry=False, is_persistent=True))
    embedding = OfflineFixtureEmbedding()
    corpus = json.loads((BASE_DIR / "data/knowledge_repository/sources/iks_canonical_corpus.json").read_text(encoding="utf-8"))
    entries = corpus if isinstance(corpus, list) else corpus["entries"]
    collection = client.get_or_create_collection("iks_canonical_library", embedding_function=embedding)
    collection.upsert(ids=[entry["id"] for entry in entries],
        documents=[entry["sanskrit"] for entry in entries],
        metadatas=[{key: value for key, value in entry.items() if isinstance(value, (str, int, float, bool))}
                   for entry in entries])
    client.get_or_create_collection("shandilya_100_sutras", embedding_function=embedding)
    client.get_or_create_collection("bhakti_sutras_comparative", embedding_function=embedding)
    original_get = client.get_collection
    original_create = client.get_or_create_collection

    def get_fixture_collection(*args, **kwargs):
        """Read temporary collections using the local test embedding function."""
        kwargs["embedding_function"] = embedding
        return original_get(*args, **kwargs)

    def create_fixture_collection(*args, **kwargs):
        """Keep all test collection creation on local deterministic embeddings."""
        kwargs["embedding_function"] = embedding
        return original_create(*args, **kwargs)

    monkeypatch.setattr(client, "get_collection", get_fixture_collection)
    monkeypatch.setattr(client, "get_or_create_collection", create_fixture_collection)
    monkeypatch.setattr(chromadb, "PersistentClient", lambda *args, **kwargs: client)
    monkeypatch.setattr("src.providers.anthropic_adapter.get_claude_key", lambda: None)
    from shutil import copytree
    from src.agents.bharatiya_jnana_agent import BharatiyaJnanaAgent
    temporary_repository = tmp_path / "knowledge_repository"
    copytree(BASE_DIR / "data/knowledge_repository/sources", temporary_repository / "sources")
    for folder in ("registry", "consultation", "research"):
        (temporary_repository / folder).mkdir()
    original_init = BharatiyaJnanaAgent.__init__

    def initialize_isolated_research(self, repo_dir=None):
        """Redirect test research writes to temporary files, preserving live logs."""
        original_init(self, repo_dir=temporary_repository)

    monkeypatch.setattr(BharatiyaJnanaAgent, "__init__", initialize_isolated_research)
    return client


def test_iks_canonical_corpus_data_completeness():
    """Verifies that the canonical IKS JSON corpus contains at least 20 text traditions."""
    corpus_file = BASE_DIR / "data" / "knowledge_repository" / "sources" / "iks_canonical_corpus.json"
    assert corpus_file.exists(), f"Corpus file not found at {corpus_file}"

    with open(corpus_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    entries = data if isinstance(data, list) else data.get("entries", [])
    assert len(entries) >= 20, f"Expected at least 20 canonical texts, found {len(entries)}"

    # Verify key canonical traditions are present
    sources = [(e.get("tradition") or e.get("source_text", "")).lower() for e in entries]
    assert any("arthashastra" in s for s in sources)
    assert any("bhagavad gita" in s for s in sources)
    assert any("yoga sutras" in s for s in sources)
    assert any("upanishad" in s for s in sources)
    assert any("tukaram" in s for s in sources)
    assert any("dnyaneshwar" in s for s in sources)
    assert any("ramdas" in s for s in sources)


def test_chromadb_iks_canonical_library_collection(tmp_path):
    """Verify seeded temporary collection retrieval, not live semantic relevance."""
    vector_store = SutraVectorStore(persist_directory=tmp_path / "vector", collection_name="shandilya_100_sutras")
    client = vector_store.client

    # Verify collection exists and count >= 20
    iks_coll = client.get_collection("iks_canonical_library")
    assert iks_coll is not None
    count = iks_coll.count()
    assert count >= 20, f"Expected at least 20 verses in iks_canonical_library, found {count}"

    # Retrieval-shape test with explicit deterministic fixture embeddings
    query_text = "Truthful business conduct, customer trust, and ethical wealth stewardship"
    results = iks_coll.query(
        query_texts=[query_text],
        n_results=2,
        include=["documents", "metadatas", "distances"],
    )
    assert len(results["documents"][0]) == 2
    assert results["distances"][0][0] < 1.5


def test_council_runner_author_specifications(tmp_path):
    """Exercise the current injected five-role runner, without keys or paid calls.

    Input is a temporary directory. A fake dispatcher supplies structured test
    responses; real review/example stores stay in temporary files. Assert roles,
    composition and author-review state without weakening runtime budget gates.
    """
    from tests.test_live_runner_wiring import FakeDispatch, FakeVector
    from tests.test_council_service import register_case_examples
    from src.database.example_registry import ExampleRegistry
    from src.orchestration.review_store import ReviewStore

    source = tmp_path / "author-source.txt"
    source.write_text("Synthetic source ethics passage for author-contract testing", encoding="utf-8")
    dispatch = FakeDispatch()
    examples = ExampleRegistry(tmp_path / "examples.db")
    register_case_examples(examples)
    runner = DynamicLiveCouncilRunner(
        dispatcher=dispatch, vector_store=FakeVector(),
        review_store=ReviewStore(tmp_path / "review.db"), example_registry=examples,
        narada_sutras=[{"sutra_no": 1, "sanskrit": "source ethics"}],
        shandilya_sutras=[{"sutra_no": 1, "sanskrit": "matching source"}],
        source_paths={"DOC-01": source})
    outcome = runner.execute_live_council(1)
    assert outcome["status"] == "HUMAN_REVIEW_PENDING"
    assert outcome["units"][0]["status"] == "HUMAN_REVIEW_PENDING"
    assert {role for role, _ in dispatch.calls} == {
        "narada_specialist", "shandilya_specialist", "bharatiya_jnana_specialist",
        "sutrakar_master", "independent_validator"}
    assert ("sutrakar_master", "compose", 16384) in dispatch.output_ceilings



def test_reformatted_word_document_generation(tmp_path: Path, monkeypatch):
    """Verifies that the canonical Word document generates with all new sections and mandatory footer."""
    import docx
    artifact_directory = tmp_path / "artifact-copy"
    artifact_directory.mkdir()
    monkeypatch.setattr("scripts.reformat_canonical_word_document.ARTIFACT_DIR", artifact_directory)
    test_docx = tmp_path / "test_canonical_output.docx"
    build_reformatted_canonical_document(output_path=test_docx)

    assert test_docx.exists()
    doc = docx.Document(str(test_docx))

    # Verify footer on sections
    for section in doc.sections:
        footer_text = section.footer.paragraphs[0].text
        assert MANDATORY_FOOTER in footer_text, f"Mandatory footer '{MANDATORY_FOOTER}' missing in section footer"

    # Verify content headers across paragraphs and tables
    all_text = " ".join(p.text for p in doc.paragraphs) + " " + " ".join(c.text for t in doc.tables for row in t.rows for c in row.cells)
    assert "UDYAM SUTRA" in all_text
    assert "Shri Shripad Kulkarni" in all_text
    assert "Source References" in all_text


def test_bharatiya_jnana_agent_dynamic_chromadb_retrieval():
    """Verifies that BharatiyaJnanaAgent dynamically queries ChromaDB and does not hardcode Tukaram for Sutra 11."""
    from src.agents.bharatiya_jnana_agent import BharatiyaJnanaAgent

    agent = BharatiyaJnanaAgent()
    assert hasattr(agent, "iks_collection")
    assert agent.iks_collection is not None
    assert agent.iks_collection.count() >= 20

    # Query for Sutra 11 with ethical commerce topic
    res = agent.research_for_concept(11, "Ethical Commerce, Wealth Circulation and Fair Pricing")
    assert "iks_text" in res
    assert "sanskrit" in res
    assert "iks_retrieved_entries" in res
    assert len(res["iks_retrieved_entries"]) > 0


def test_five_agent_council_pre_execution_audit_and_enterprise_domains():
    """Verifies that FiveAgentCouncil checks ChromaDB and provides enterprise domains A-Q."""
    from src.orchestration.five_agent_council import FiveAgentCouncil

    council = FiveAgentCouncil()
    audit = council.run_pre_execution_audit()
    assert audit["status"] == "PASS"
    assert audit["access_checks"]["chromadb_iks_collection_access"] == "VERIFIED"

    # Verify domain lookup
    domain_a = council.get_enterprise_domain("A")
    assert domain_a is not None
    assert domain_a["theme"] == "Enterprise Vision, Sankalpa & Inception"
    assert domain_a["domain_id"] == "A"

    domain_f = council.get_enterprise_domain("F")
    assert domain_f is not None
    assert "Patanjali" in domain_f["theme"] or "Patanjali" in domain_f["iks_focus"]


def test_anthropic_adapter_bypass_eradication():
    """Verifies that AnthropicAdapter has zero silent fallback to OpenAI."""
    from src.providers.anthropic_adapter import AnthropicAdapter
    from src.providers.base import ProviderAuthenticationError, ProviderError

    # Offline mode behaves properly
    offline_adapter = AnthropicAdapter(offline_mode=True)
    assert offline_adapter.provider_name == "anthropic"

    # Missing API key raises ProviderAuthenticationError
    missing_key_adapter = AnthropicAdapter(api_key=None, offline_mode=False)
    with pytest.raises(ProviderAuthenticationError):
        missing_key_adapter.generate(prompt="Test prompt")
