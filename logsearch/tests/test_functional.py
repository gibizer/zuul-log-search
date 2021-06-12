import contextlib
import io
import sys
from typing import Generator
import unittest
from unittest import mock

from logsearch import main
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


class TestBuildList(unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.build1 = {
            "uuid": "fake-uuid",
            "ref_url": "fake-url",
            "patchset": "1",
        }
        self.build2 = {
            "uuid": "fake-uuid2",
            "ref_url": "fake-url2",
            "patchset": "3",
        }

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
