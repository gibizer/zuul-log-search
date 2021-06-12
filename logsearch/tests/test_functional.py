import contextlib
import io
import sys
import tempfile
from typing import Generator
import unittest
from unittest import mock

from logsearch import main
from logsearch import search
from logsearch.tests import fakes
from logsearch import zuul


@contextlib.contextmanager
def collect_stdout() -> Generator[io.StringIO, None, None]:
    stdout = io.StringIO()
    orig_stdout = sys.stdout
    sys.stdout = stdout
    try:
        yield stdout
    finally:
        sys.stdout = orig_stdout


class TestBase(unittest.TestCase):
    def setUp(self) -> None:
        super(TestBase, self).setUp()
        self.build1 = {
            "uuid": "fake-uuid",
            "ref_url": "fake-url",
            "patchset": "1",
            "end_time": "fake-date",
            "project": "fake-project",
            "branch": "fake-branch",
            "job_name": "fake-job",
            "pipeline": "fake-pipeline",
            "result": "fake-result",
            "log_url": "fake-log-url",
        }
        self.build2 = {
            "uuid": "fake-uuid2",
            "ref_url": "fake-url2",
            "patchset": "3",
        }


class TestBuildList(TestBase):
    def setUp(self):
        super().setUp()

    @mock.patch("logsearch.zuul.API.list_builds")
    def test_default(self, mock_zuul_list_builds):
        mock_zuul_list_builds.return_value = [self.build1]

        with collect_stdout() as stdout:
            main.main(args=["build"])

        output = stdout.getvalue()
        self.assertIn("fake-uuid", output)
        self.assertIn("fake-url/1", output)
        mock_zuul_list_builds.assert_called_once_with(
            "openstack", None, None, [], [], None, None, 10
        )

    @mock.patch("logsearch.zuul.API.list_builds")
    def test_default_multiple_result(self, mock_zuul_list_builds):
        mock_zuul_list_builds.return_value = [self.build1, self.build2]

        with collect_stdout() as stdout:
            main.main(args=["build"])

        output = stdout.getvalue()
        self.assertIn("fake-uuid", output)
        self.assertIn("fake-url/1", output)
        self.assertIn("fake-uuid2", output)
        self.assertIn("fake-url2/3", output)
        mock_zuul_list_builds.assert_called_once_with(
            "openstack", None, None, [], [], None, None, 10
        )

    @mock.patch("logsearch.zuul.API.list_builds")
    def test_query_args_with_repetition(self, mock_zuul_list_builds):
        mock_zuul_list_builds.return_value = [self.build1]

        with collect_stdout() as stdout:
            main.main(
                args=[
                    "build",
                    "--project",
                    "nova",
                    "--job",
                    "nova-grenade-multinode",
                    "--job",
                    "nova-next",
                    "--branch",
                    "master",
                    "--branch",
                    "stable/wallaby",
                    "--result",
                    "FAILURE",
                    "--pipeline",
                    "gate",
                    "--voting",
                    "--limit",
                    "3",
                ]
            )

        output = stdout.getvalue()
        self.assertIn("fake-uuid", output)
        self.assertIn("fake-url/1", output)
        mock_zuul_list_builds.assert_called_once_with(
            "openstack",
            "nova",
            "gate",
            ["nova-grenade-multinode", "nova-next"],
            ["master", "stable/wallaby"],
            "FAILURE",
            True,
            3,
        )

    @mock.patch("logsearch.zuul.API.list_builds")
    def test_zuul_api_error(self, mock_zuul_list_builds):
        mock_zuul_list_builds.side_effect = zuul.ZuulException()

        with collect_stdout() as stdout:
            main.main(args=["build"])

        output = stdout.getvalue()
        self.assertIn("Cannot access Zuul", output)
        mock_zuul_list_builds.assert_called_once_with(
            "openstack", None, None, [], [], None, None, 10
        )


class TestBuildShow(TestBase):
    def setUp(self) -> None:
        super().setUp()

    def test_cached(self):
        with tempfile.TemporaryDirectory() as cache_dir:
            cache = search.BuildLogCache(cache_dir, mock.Mock(spec=zuul.API))
            cache._cache_build_meta(self.build1)

            with collect_stdout() as stdout:
                main.main(
                    args=[
                        "--log_store_dir",
                        cache_dir,
                        "build-show",
                        "fake-uuid",
                    ]
                )

        output = stdout.getvalue()
        self.assertIn("fake-uuid", output)
        self.assertIn("fake-url/1", output)

    def test_not_cached(self):
        with collect_stdout() as stdout:
            main.main(args=["build-show", "fake-uuid"])

        output = stdout.getvalue()
        self.assertIn("Build fake-uuid is not cached", output)


class TestLogSearch(TestBase):
    @mock.patch("logsearch.zuul.API")
    def test_one_build_default_file(self, mock_zuul):
        fake_zuul = fakes.FakeZuul()
        mock_zuul.return_value = fake_zuul
        fake_zuul.set_builds([self.build1])
        fake_zuul.add_log_content(
            self.build1["uuid"],
            "job-output.txt",
            "foo\n"
            "... some-pattern and bar\n"
            "baz\n"
            "another some-pattern instance\n",
        )

        with tempfile.TemporaryDirectory() as cache_dir:
            with collect_stdout() as stdout:
                main.main(
                    args=[
                        "--log_store_dir",
                        cache_dir,
                        "log",
                        "some-pattern",
                    ]
                )

        output = stdout.getvalue()
        self.assertIn("fake-uuid:2:... some-pattern and bar", output)
        self.assertIn("fake-uuid:4:another some-pattern instance", output)
        self.assertIn("fake-uuid", output)
        self.assertIn("fake-url/1", output)
        self.assertIn("1/1", output)

    @mock.patch("logsearch.zuul.API")
    def test_one_build_default_file_no_match(self, mock_zuul):
        fake_zuul = fakes.FakeZuul()
        mock_zuul.return_value = fake_zuul
        fake_zuul.set_builds([self.build1])
        fake_zuul.add_log_content(
            self.build1["uuid"],
            "job-output.txt",
            "foo\n"
            "... some-pattern and bar\n"
            "baz\n"
            "another some-pattern instance\n",
        )

        with tempfile.TemporaryDirectory() as cache_dir:
            with collect_stdout() as stdout:
                main.main(
                    args=[
                        "--log_store_dir",
                        cache_dir,
                        "log",
                        "non-matching-pattern",
                    ]
                )

        output = stdout.getvalue()
        self.assertNotIn("pattern", output)
        self.assertIn("fake-uuid", output)
        self.assertIn("fake-url/1", output)
        self.assertIn("0/1", output)
