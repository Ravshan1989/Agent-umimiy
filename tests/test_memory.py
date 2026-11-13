import tempfile
import unittest
from pathlib import Path

from agent_umimiy import memory


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.alice = self.root / "alice.json"
        self.bob = self.root / "bob.json"

    def test_memory_files_are_isolated(self):
        result = memory.remember("Ali ma'lumoti", self.alice)
        self.assertIn("saqlandi", result.lower())
        self.assertIn("Ali ma'lumoti", memory.search("Ali", path=self.alice))
        self.assertNotIn("Ali ma'lumoti", memory.search("Ali", path=self.bob))
        item_id = memory.list_items(self.alice)[0]["id"]
        self.assertIn("topilmadi", memory.forget(item_id, self.bob).lower())
        self.assertEqual(len(memory.list_items(self.alice)), 1)
        self.assertIn("o'chirildi", memory.forget(item_id, self.alice).lower())
        self.assertEqual(memory.list_items(self.alice), [])

    def test_maximum_does_not_silently_drop_old_entries(self):
        memory._write(self.alice, [{"id": str(i), "fact": f"fact {i}"} for i in range(memory.MAX_ITEMS)])
        result = memory.remember("yangi fakt", self.alice)
        self.assertIn("limiti", result.lower())
        self.assertEqual(len(memory.list_items(self.alice)), memory.MAX_ITEMS)
        self.assertEqual(memory.list_items(self.alice)[0]["fact"], "fact 0")


if __name__ == "__main__":
    unittest.main()
