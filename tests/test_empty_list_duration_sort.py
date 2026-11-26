import unittest

from ls_core.service import duration_sort_value
import ls_library.render as render


class DurationSortRenderRegressionTest(unittest.TestCase):
    def test_library_render_has_duration_sort_callable(self):
        self.assertTrue(callable(render.duration_sort_value))
        self.assertIs(render.duration_sort_value, duration_sort_value)
        self.assertEqual(render.duration_sort_value("1:23"), 83.0)
        self.assertEqual(render.duration_sort_value("1:02:03"), 3723.0)


if __name__ == "__main__":
    unittest.main()
