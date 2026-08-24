import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services import material_retrieval


class TestMaterialRetrievalPlanning(unittest.TestCase):
    def setUp(self):
        self.terms = [
            "customer entering convenience store",
            "shopper browsing small grocery aisle",
            "organized convenience store shelves",
            "commuter grabbing breakfast food",
            "customer choosing hot food",
            "seasonal snacks on store shelf",
            "shopper comparing packaged products",
            "customer leaving with shopping bag",
        ]

    def test_infers_specific_shared_store_context(self):
        self.assertEqual(
            material_retrieval.infer_shared_context(self.terms),
            "convenience store",
        )

    def test_expands_broad_intent_with_shared_context(self):
        variants = material_retrieval.build_search_variants(
            "customer choosing hot food",
            "convenience store",
        )

        self.assertEqual(variants[0], "convenience store hot food")
        self.assertIn("customer choosing hot food", variants)
        self.assertIn("hot food", variants)

    def test_rejects_obvious_restaurant_scene_for_store_context(self):
        self.assertTrue(
            material_retrieval.is_obvious_metadata_mismatch(
                "https://www.pexels.com/video/woman-eating-at-a-restaurant-123/",
                "customer choosing hot food",
                "convenience store",
            )
        )

    def test_keeps_matching_store_scene(self):
        self.assertFalse(
            material_retrieval.is_obvious_metadata_mismatch(
                "https://www.pexels.com/video/customer-buying-food-in-a-store-123/",
                "customer choosing hot food",
                "convenience store",
            )
        )


class TestMaterialRetrievalIntegration(unittest.TestCase):
    def _item(self, url, source_page, asset_id):
        return SimpleNamespace(
            provider="pexels",
            url=url,
            duration=8,
            source_info={
                "provider": "pexels",
                "search_term": "seed",
                "asset_id": asset_id,
                "source_page": source_page,
            },
        )

    def test_installed_downloader_searches_context_anchored_variants(self):
        baseline = Mock(return_value=["baseline.mp4"])
        persisted = []
        saved_urls = []
        fake_material = SimpleNamespace(
            _download_videos_by_script_order=baseline,
            _material_source_record=lambda item, local_path: {
                "provider": item.provider,
                "local_file": local_path,
            },
            save_video=lambda video_url, save_dir="": saved_urls.append(video_url)
            or f"/tmp/{len(saved_urls)}.mp4",
            _persist_material_sources=lambda task_id, records: persisted.extend(records),
            _redact_request_error=lambda error, *secrets: str(error),
        )
        material_retrieval.install(fake_material)

        search_calls = []

        def search_videos(search_term, minimum_duration, video_aspect):
            search_calls.append(search_term)
            if search_term == "convenience store hot food":
                return [
                    self._item(
                        "https://cdn.example/good.mp4",
                        "https://www.pexels.com/video/customer-buying-food-in-store-1/",
                        "good",
                    ),
                    self._item(
                        "https://cdn.example/bad.mp4",
                        "https://www.pexels.com/video/woman-eating-at-restaurant-2/",
                        "bad",
                    ),
                ]
            return []

        result = fake_material._download_videos_by_script_order(
            task_id="task-1",
            search_terms=[
                "customer entering convenience store",
                "shopper browsing grocery store aisle",
                "customer choosing hot food",
                "seasonal snacks on store shelf",
            ],
            search_videos=search_videos,
            video_aspect="9:16",
            audio_duration=2,
            max_clip_duration=3,
            material_directory="/tmp",
        )

        self.assertIn("convenience store hot food", search_calls)
        self.assertNotIn("https://cdn.example/bad.mp4", saved_urls)
        self.assertEqual(result, ["/tmp/1.mp4"])
        self.assertEqual(persisted[0]["visual_intent"], "customer choosing hot food")
        self.assertEqual(persisted[0]["query_variant"], "convenience store hot food")
        baseline.assert_not_called()


if __name__ == "__main__":
    unittest.main()
