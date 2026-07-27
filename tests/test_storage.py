import tempfile
import unittest
from pathlib import Path

from feniks.api import DesktopApi
from feniks.storage import Storage


class ApplicationDataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "test.db"
        self.storage = Storage(self.path)
        self.api = DesktopApi(self.storage)

    def tearDown(self):
        self.storage.connection.close()
        self.temp.cleanup()

    def create_agent(self):
        result = self.api.create_agent({"name": "Мой агент", "category": "game",
                                        "description": "Тест", "mode": "observer"})
        self.assertTrue(result["ok"])
        return result["agent"]

    def test_new_workspace_has_no_demo_agents(self):
        self.assertEqual(self.api.bootstrap()["agents"], [])

    def test_agent_chat_and_message_survive_restart(self):
        agent = self.create_agent()
        chat = self.api.create_chat(agent["id"], "Первая вселенная")["chat"]
        saved = self.api.send_message(agent["id"], chat["id"], "Запомни это")
        self.assertTrue(saved["ok"])
        self.storage.connection.close()

        self.storage = Storage(self.path)
        self.api = DesktopApi(self.storage)
        self.assertEqual(self.api.bootstrap()["agents"][0]["name"], "Мой агент")
        self.assertEqual(self.api.get_chats(agent["id"])[0]["title"], "Первая вселенная")
        self.assertEqual(self.api.get_messages(chat["id"])[0]["content"], "Запомни это")

    def test_chat_copy_creates_independent_history(self):
        agent = self.create_agent()
        original = self.api.create_chat(agent["id"], "Оригинал")["chat"]
        self.api.send_message(agent["id"], original["id"], "Исходный контекст")
        branch = self.api.create_chat(agent["id"], "Ветка", original["id"], "copy")["chat"]
        self.api.send_message(agent["id"], branch["id"], "Только в ветке")
        self.assertEqual(len(self.api.get_messages(original["id"])), 1)
        self.assertEqual(len(self.api.get_messages(branch["id"])), 2)

    def test_delete_agent_cascades_chats_and_messages(self):
        agent = self.create_agent()
        chat = self.api.create_chat(agent["id"], "Чат")["chat"]
        self.api.send_message(agent["id"], chat["id"], "Сообщение")
        self.assertTrue(self.api.delete_agent(agent["id"])["ok"])
        self.assertEqual(self.api.get_chats(agent["id"]), [])
        self.assertEqual(self.api.get_messages(chat["id"]), [])

    def test_validation_rejects_bad_values(self):
        self.assertFalse(self.api.create_agent({"name": "", "mode": "root"})["ok"])
        self.assertFalse(self.api.set_agent_mode("missing", "unlimited")["ok"])
        self.assertFalse(self.api.save_setting("api_secret", "value")["ok"])

    def test_resources_survive_restart_and_keep_their_kind(self):
        self.assertTrue(self.api.create_resource(
            {"kind": "model", "name": "Local model", "config": {"path": "model.gguf"}})["ok"])
        self.assertTrue(self.api.create_resource(
            {"kind": "dataset", "name": "Examples", "config": {}})["ok"])
        self.assertEqual(self.storage.resources("model")[0]["name"], "Local model")
        self.storage.connection.close()
        self.storage = Storage(self.path)
        self.api = DesktopApi(self.storage)
        self.assertEqual(len(self.api.bootstrap()["resources"]), 2)


if __name__ == "__main__":
    unittest.main()
