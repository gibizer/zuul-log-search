import os.path
import tempfile
from typing import List
import unittest
from unittest import mock

import requests

from logsearch import search
from logsearch import zuul


class FakeZuul(zuul.API):
    def __init__(self) -> None:
        super().__init__("fake_zuul_url")
        self.fetched_files: List[str] = []

    def fetch_log(self, build, log_file, local_path, progress_handler):
        with open(local_path, "w") as f:
            f.write("fake log data")
        self.fetched_files.append(log_file)


class TestBuildLogCache(unittest.TestCase):
    def test_ensure_build_log_file_needs_to_fetch(self):
        build = {"uuid": "fake_uuid", "log_url": "http://fake_log_url/"}
        fake_zuul = FakeZuul()
        with tempfile.TemporaryDirectory() as cache_dir:
            cache = search.BuildLogCache(cache_dir, fake_zuul)

            local_path = cache.ensure_build_log_file(build, "log-file-path")

            self.assertEqual(["log-file-path"], fake_zuul.fetched_files)
            self.assertTrue(local_path.endswith("fake_uuid/log-file-path"))

    def test_ensure_build_log_already_cached(self):
        build = {"uuid": "fake_uuid", "log_url": "http://fake_log_url/"}
        fake_zuul = FakeZuul()
        with tempfile.TemporaryDirectory() as cache_dir:
            cache = search.BuildLogCache(cache_dir, fake_zuul)
            # download it once
            local_path = cache.ensure_build_log_file(build, "log-file-path")
            # but not the second time
            local_path = cache.ensure_build_log_file(build, "log-file-path")
            # file only downloaded once
            self.assertEqual(["log-file-path"], fake_zuul.fetched_files)
            self.assertTrue(local_path.endswith("fake_uuid/log-file-path"))
            self.assertTrue(os.path.exists(local_path))

    def test_ensure_build_log_file_download_fails(self):
        build = {"uuid": "fake_uuid", "log_url": "http://fake_log_url/"}
        mock_zuul = mock.Mock(spec=zuul.API)
        mock_zuul.fetch_log.side_effect = requests.HTTPError()

        with tempfile.TemporaryDirectory() as cache_dir:
            cache = search.BuildLogCache(cache_dir, mock_zuul)

            local_path = cache.ensure_build_log_file(build, "log-file-path")

            mock_zuul.fetch_log.assert_called_once_with(
                build,
                "log-file-path",
                os.path.join(cache_dir, "fake_uuid/log-file-path"),
                mock.ANY,
            )
            self.assertIsNone(local_path)


class TestSearch(unittest.TestCase):
    def _test_search(
        self,
        log_lines,
        regex,
        expected_match_lines,
        before_context=None,
        after_context=None,
        context=None,
    ):
        with tempfile.NamedTemporaryFile() as f:
            f.write("\n".join(log_lines).encode())
            f.flush()

            ls = search.LogSearch()
            lines = ls.get_matches(
                {f.name},
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
