import tempfile
import unittest
from pathlib import Path

from feniks.api import DesktopApi
from feniks.storage import Storage


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.storage = Storage(Path(self.temp.name) / "test.db")
        self.api = DesktopApi(self.storage)

    def tearDown(self):
        self.storage.connection.close()
        self.temp.cleanup()

    def test_default_agents_are_separate_entities(self):
        agents = self.api.bootstrap()["agents"]
        self.assertEqual(len(agents), 3)
        self.assertEqual({agent["id"] for agent in agents},
                         {"stellaris-advisor", "desktop-copilot", "factory-planner"})

    def test_chat_and_structured_log_are_persisted(self):
        result = self.api.send_message("stellaris-advisor", "Проанализируй экономику")
        self.assertTrue(result["ok"])
        self.assertEqual(len(self.api.get_messages("stellaris-advisor")), 2)
        log = self.api.get_logs()[0]
        self.assertEqual(log["category"], "agent.task")
        self.assertEqual(log["payload"]["status"], "queued")

    def test_rejects_unknown_autonomy_mode(self):
        self.assertFalse(self.api.set_agent_mode("stellaris-advisor", "unlimited")["ok"])


if __name__ == "__main__":
    unittest.main()
