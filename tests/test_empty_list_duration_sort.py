import unittest
from unittest.mock import patch

from ls_core.service import duration_sort_value
import ls_library.render as render


class DurationSortRenderRegressionTest(unittest.TestCase):
    def test_library_render_has_duration_sort_callable(self):
        self.assertTrue(callable(render.duration_sort_value))
        self.assertIs(render.duration_sort_value, duration_sort_value)
        self.assertEqual(render.duration_sort_value("1:23"), 83.0)
        self.assertEqual(render.duration_sort_value("1:02:03"), 3723.0)


class LibraryLocalAudioPathRegressionTest(unittest.TestCase):
    def test_render_uses_resolved_local_audio_without_row_local_columns(self):
        row = {
            "id": "track-1",
            "title": "Test track",
            "workspace": "",
            "audio_url": "https://example.invalid/audio.mp3",
            "created_at": "2026-01-01T00:00:00Z",
            "duration": 61,
        }
        with (
            patch.object(render, "get_track_local_family_titles", return_value={}),
            patch.object(render, "build_track_thumbnail_html", return_value=""),
        ):
            html = "\n".join(render.build_library_table_rows(
                rows=[row],
                stem_counts={},
                confirmed_local_audio_paths={},
                local_audio_paths={"track-1": r"E:\\Music\\Test.mp3"},
                selection_view_active=False,
                kind_filter="",
            ))

        self.assertIn('data-local-mp3="E:\\Music\\Test.mp3"', html)
        self.assertIn('data-local-wav=""', html)


if __name__ == "__main__":
    unittest.main()
