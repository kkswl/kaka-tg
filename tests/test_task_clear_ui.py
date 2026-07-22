import unittest
from pathlib import Path


PAGE_PATH = Path(__file__).resolve().parents[1] / "plugins.v2" / "tgsearch115" / "frontend" / "src" / "components" / "Page.vue"


class TaskClearUiTest(unittest.TestCase):
    def setUp(self):
        self.source = PAGE_PATH.read_text(encoding="utf-8")

    def test_clear_action_has_accessible_label_and_confirmation_dialog(self):
        self.assertIn('aria-label="清除已结束的磁力下载任务记录"', self.source)
        self.assertIn('v-model="clearTasksDialog"', self.source)
        self.assertIn('确认清除任务记录', self.source)
        self.assertIn('不会删除 115 文件，不会取消离线下载，也不会修改订阅。', self.source)

    def test_clear_request_sends_explicit_confirmation(self):
        self.assertIn('tasks/clear`, { confirm: true }', self.source)
        self.assertIn('terminalTaskCount', self.source)
        self.assertIn('activeTaskCount', self.source)


if __name__ == "__main__":
    unittest.main()
