"""Offline SQLite behavior checks independent of optional application packages."""

import tempfile
import unittest
import importlib.util
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

module_path = Path(__file__).resolve().parents[1] / "src" / "database" / "example_registry.py"
spec = importlib.util.spec_from_file_location("example_registry_standalone", module_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
ExampleRegistry = module.ExampleRegistry


class ExampleRegistryTests(unittest.TestCase):
    """Exercise durable identity and cross-chapter reservation boundaries."""

    def test_alias_repeat_restart_and_same_chapter(self):
        """A new handle retains allocations; alias reuse across chapters fails."""
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "examples.db"
            registry = ExampleRegistry(path)
            registry.register("Jamsetji Tata", "PERSON", "documented biography", ["J. Tata"])
            registry.reserve("1", [{"name": "Jamsetji Tata", "polarity": "POSITIVE", "location": "case"},
                                   {"name": "J. Tata", "polarity": "POSITIVE", "location": "commentary"}], "hash-one")
            resumed = ExampleRegistry(path)
            with self.assertRaises(ValueError):
                resumed.reserve("2", [{"name": "J. Tata", "polarity": "POSITIVE", "location": "DO"}], "hash-two")
            resumed.release("1")
            resumed.reserve("2", [{"name": "J. Tata", "polarity": "POSITIVE", "location": "DO"}], "hash-two")

    def test_exception_requires_author_record(self):
        """Only a complete, chapter-specific exception permits a repeated identity."""
        with tempfile.TemporaryDirectory() as folder:
            registry = ExampleRegistry(Path(folder) / "examples.db")
            registry.register("Tata Group", "BUSINESS", "company history", ["Tata"])
            registry.reserve("1", [{"name": "Tata", "polarity": "POSITIVE", "location": "case"}], "hash-one")
            with self.assertRaises(ValueError):
                registry.approve_exception("2", "Tata", '["1"]', "", "none", "needed", "Author", "hash-two")
            registry.approve_exception("2", "Tata", '["1"]', "distinct documented event",
                                       "alternatives reviewed", "necessary to explain principle", "Author", "hash-two")
            registry.reserve("2", [{"name": "Tata Group", "polarity": "CAUTIONARY", "location": "DONT"}], "hash-two")

    def test_related_identity_and_stale_exception(self):
        """A founder-company link and changed chapter hash require fresh author review."""
        with tempfile.TemporaryDirectory() as folder:
            registry = ExampleRegistry(Path(folder) / "examples.db")
            registry.register("Founder One", "PERSON", "biography")
            registry.register("Company One", "BUSINESS", "company history")
            registry.relate("Founder One", "Company One", "founder")
            registry.reserve("1", [{"name": "Founder One", "polarity": "POSITIVE", "location": "case"}], "hash-a")
            entry = [{"name": "Company One", "polarity": "POSITIVE", "location": "case"}]
            with self.assertRaises(ValueError):
                registry.reserve("2", entry, "hash-b")
            registry.approve_exception("2", "Company One", '["1"]', "distinct event",
                                       "alternatives considered", "necessary", "Author", "hash-b")
            registry.reserve("2", entry, "hash-b")
            with self.assertRaises(ValueError):
                registry.reserve("2", entry, "hash-c")

    def test_incorrect_prior_chapter_set_rejected(self):
        """An exception with an incomplete prior chapter list does not waive reuse."""
        with tempfile.TemporaryDirectory() as folder:
            registry = ExampleRegistry(Path(folder) / "examples.db")
            registry.register("Founder One", "PERSON", "biography")
            entry = [{"name": "Founder One", "polarity": "POSITIVE", "location": "case"}]
            registry.reserve("1", entry, "hash-a")
            registry.approve_exception("2", "Founder One", '["3"]', "distinct event",
                                       "alternatives considered", "necessary", "Author", "hash-b")
            with self.assertRaises(ValueError):
                registry.reserve("2", entry, "hash-b")

    def test_concurrent_chapters_cannot_both_claim_entity(self):
        """Immediate transactions serialize claims across independent registry handles."""
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "examples.db"
            ExampleRegistry(path).register("Founder One", "PERSON", "biography")

            def claim(chapter):
                """Reserve one contender; return success or expected conflict for test diagnostics."""
                try:
                    ExampleRegistry(path).reserve(chapter, [
                        {"name": "Founder One", "polarity": "POSITIVE", "location": "case"}], f"hash-{chapter}")
                    return True
                except ValueError:
                    return False

            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(claim, ("1", "2")))
            self.assertEqual(sorted(results), [False, True])


if __name__ == "__main__":
    unittest.main()
