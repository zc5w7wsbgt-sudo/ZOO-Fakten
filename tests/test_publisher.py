import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("publisher", ROOT / "instagram_publisher.py")
publisher = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(publisher)


class ValidationTests(unittest.TestCase):
    def good_post(self):
        return {
            "id": "test",
            "status": "approved",
            "scheduled_at": "2026-08-28T18:00:00+02:00",
            "caption": "Belegter Beitrag #ZooFakten",
            "media": [{"type": "IMAGE", "url": "https://example.org/image.jpg"}],
        }

    def test_valid_post(self):
        self.assertEqual(publisher.validate_post(self.good_post()), [])

    def test_rejects_missing_timezone(self):
        post = self.good_post()
        post["scheduled_at"] = "2026-08-28T18:00:00"
        self.assertTrue(any("Zeitzone" in error for error in publisher.validate_post(post)))

    def test_rejects_too_many_media_items(self):
        post = self.good_post()
        post["media"] *= 11
        self.assertTrue(any("1 bis 10" in error for error in publisher.validate_post(post)))

    def test_rejects_long_caption(self):
        post = self.good_post()
        post["caption"] = "x" * 2201
        self.assertTrue(any("maximal" in error for error in publisher.validate_post(post)))


if __name__ == "__main__":
    unittest.main()
