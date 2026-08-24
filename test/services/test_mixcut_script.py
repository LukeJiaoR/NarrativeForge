import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services import llm


class TestMixcutScriptPrompt(unittest.TestCase):
    def test_default_prompt_requires_short_video_structure(self):
        prompt = llm.build_script_prompt(
            video_subject="为什么很多人第一次去日本会觉得便利店很好逛",
            language="zh-CN",
            paragraph_number=2,
        )

        self.assertIn("Mixcut Short-Video Copywriter", prompt)
        self.assertIn("1-2 second hook", prompt)
        self.assertIn("clear point of view", prompt)
        self.assertIn("2-3 noticeable escalations", prompt)
        self.assertIn("concrete, visualizable detail", prompt)
        self.assertIn("25-45 seconds", prompt)
        self.assertIn("- video subject: 为什么很多人第一次去日本会觉得便利店很好逛", prompt)

    def test_normalize_text_response_preserves_script_paragraphs(self):
        result = llm._normalize_text_response(
            "第一句就是钩子。\r\n\r\n第二段继续递进。\n\n\n最后一句收住。",
            "openai",
        )

        self.assertEqual(
            result,
            "第一句就是钩子。\n\n第二段继续递进。\n\n最后一句收住。",
        )


if __name__ == "__main__":
    unittest.main()
