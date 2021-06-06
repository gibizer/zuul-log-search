import tempfile
from typing import List
import unittest

from logsearch import search
from logsearch import zuul


class FakeZuul(zuul.API):
    def __init__(self, lines: List[str]) -> None:
        super().__init__("fake_zuul_url")
        self.file_content = "\n".join(lines)
        self.fetched_files: List[str] = []

    def fetch_log(self, build, log_file, local_path, progress_handler):
        with open(local_path, "w") as f:
            f.write(self.file_content)
        self.fetched_files.append(log_file)


class TestSearch(unittest.TestCase):
    def setUp(self):
        self.build = {
            "uuid": "build-1",
        }

    def _test_search(
        self,
        log_lines,
        regex,
        expected_match_lines,
        before_context=None,
        after_context=None,
        context=None,
    ):
        fake_zuul = FakeZuul(lines=log_lines)
        with tempfile.TemporaryDirectory() as temp_dir:
            ls = search.LogSearch(search.BuildLogCache(temp_dir, fake_zuul))
            lines = ls.get_matches(
                self.build,
                "fake_file_path",
                regex,
                before_context,
                after_context,
                context,
            )

        self.assertEqual(
            len(expected_match_lines),
            len(lines),
            f"Expected:{expected_match_lines}\nActual:{lines}",
        )
        for expected, actual in zip(expected_match_lines, lines):
            self.assertEqual(expected, actual)

        self.assertEqual(1, len(fake_zuul.fetched_files))
        self.assertEqual("fake_file_path", fake_zuul.fetched_files[0])

    def test_no_match(self):
        self._test_search(
            log_lines=[
                "line1 a",
                "line2 b",
                "line3 c",
            ],
            regex="d",
            expected_match_lines=[],
        )

    def test_no_context(self):
        self._test_search(
            log_lines=[
                "line1 a",
                "line2 b",
                "line3 c",
                "line4 b",
            ],
            regex="b",
            expected_match_lines=[
                "2:line2 b",
                "4:line4 b",
            ],
        )

    def test_before_context_single_match(self):
        self._test_search(
            log_lines=[
                "line1 a",
                "line2 b",
                "line3 c",
            ],
            regex="b",
            expected_match_lines=[
                "1-line1 a",
                "2:line2 b",
            ],
            before_context=1,
        )

    def test_before_context_two_consecutive_matches(self):
        self._test_search(
            log_lines=[
                "line1 a",
                "line2 b",
                "line3 c",
                "line4 b",
            ],
            regex="b",
            expected_match_lines=[
                "1-line1 a",
                "2:line2 b",
                "3-line3 c",
                "4:line4 b",
            ],
            before_context=1,
        )

    def test_before_context_two_non_consecutive_matches(self):
        self._test_search(
            log_lines=[
                "line1 a",
                "line2 b",
                "line3 c",
                "line4 c",
                "line5 b",
            ],
            regex="b",
            expected_match_lines=[
                "1-line1 a",
                "2:line2 b",
                "--",
                "4-line4 c",
                "5:line5 b",
            ],
            before_context=1,
        )
