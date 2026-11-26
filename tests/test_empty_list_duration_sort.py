import inspect
import unittest

from ls_core.service import duration_sort_value
import ls_library.render as render


class DurationSortRenderRegressionTest(unittest.TestCase):
    def test_library_render_has_duration_sort_callable(self):
        self.assertTrue(callable(render.duration_sort_value))
        self.assertIs(render.duration_sort_value, duration_sort_value)
        self.assertEqual(render.duration_sort_value("1:23"), 83.0)
        self.assertEqual(render.duration_sort_value("1:02:03"), 3723.0)


class LibraryLocalAudioPathRegressionTest(unittest.TestCase):
    def test_render_does_not_require_legacy_local_audio_row_columns(self):
        source = inspect.getsource(render.build_library_table_rows)
        self.assertNotIn('row["local_mp3"]', source)
        self.assertNotIn('row["local_wav"]', source)
        self.assertIn("local_audio_paths.get", source)
        self.assertIn('endswith(".wav")', source)
        self.assertIn('endswith(".mp3")', source)


if __name__ == "__main__":
    unittest.main()
