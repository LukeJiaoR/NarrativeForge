import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services import material


class TestServicesInitialization(unittest.TestCase):
    def test_mixcut_retrieval_hook_is_installed(self):
        self.assertTrue(getattr(material, "_mixcut_retrieval_installed", False))


if __name__ == "__main__":
    unittest.main()
