import contextlib
import io
import unittest
from unittest.mock import patch

from ipc_lab.__main__ import main


class EntrypointTests(unittest.TestCase):
    def test_check_without_starting_ui(self):
        with patch("sys.argv", ["explore", "--check"]), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(), 0)
        self.assertIn("Lab ready", output.getvalue())

    def test_missing_dependency_guidance(self):
        with patch("sys.argv", ["explore", "--check"]), patch("importlib.util.find_spec", return_value=None), contextlib.redirect_stderr(io.StringIO()) as output:
            self.assertEqual(main(), 1)
        self.assertIn("requirements-lab.txt", output.getvalue())

    def test_missing_release_guidance(self):
        with patch("sys.argv", ["explore", "--check"]), patch("pathlib.Path.is_file", return_value=False), contextlib.redirect_stderr(io.StringIO()) as output:
            self.assertEqual(main(), 1)
        self.assertIn("make release", output.getvalue())

    def test_noninteractive_terminal_guidance(self):
        with patch("sys.argv", ["explore"]), patch("sys.stdin.isatty", return_value=False), contextlib.redirect_stderr(io.StringIO()) as output:
            self.assertEqual(main(), 1)
        self.assertIn("interactive terminal", output.getvalue())
