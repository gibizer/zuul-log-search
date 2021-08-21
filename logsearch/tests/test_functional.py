import contextlib
import io
import os
import sys
import tempfile
from typing import Generator, Dict, Iterable
import unittest
from unittest import mock
import yaml

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


@contextlib.contextmanager
def test_config(config: Dict) -> Generator[str, None, None]:
    with tempfile.TemporaryDirectory() as config_dir:
        with open(os.path.join(config_dir, "my-test-config.conf"), "w") as f:
            yaml.dump(config, f)

        yield config_dir


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
            "end_time": "fake-date",
            "project": "fake-project",
            "branch": "fake-branch",
            "job_name": "fake-job",
            "pipeline": "fake-pipeline",
            "result": "fake-result",
            "log_url": "fake-log-url",
        }

    @staticmethod
    def _run_cli(config: Dict = None, args: Iterable[str] = ()) -> str:
        with collect_stdout() as stdout:
            with test_config(config or {}) as config_dir:
                with tempfile.TemporaryDirectory() as cache_dir:
                    main.main(
                        args=[
                            "--config-dir",
                            config_dir,
                            "--log-store-dir",
                            cache_dir,
                            *args,
                        ]
                    )
        return stdout.getvalue()


class TestBuildList(TestBase):
    def setUp(self):
        super().setUp()

    @mock.patch("logsearch.zuul.API.list_builds")
    def test_default(self, mock_zuul_list_builds):
        mock_zuul_list_builds.return_value = [self.build1]

        output = self._run_cli(args=["build"])

        self.assertIn("fake-uuid", output)
        self.assertIn("fake-url", output)
        mock_zuul_list_builds.assert_called_once_with(
            "openstack",
            None,
            None,
            set(),
            [],
            None,
            None,
            10,
            None,
            None,
        )

    @mock.patch("logsearch.zuul.API.list_builds")
    def test_default_multiple_result(self, mock_zuul_list_builds):
        mock_zuul_list_builds.return_value = [self.build1, self.build2]

        output = self._run_cli(args=["build"])

        self.assertIn("fake-uuid", output)
        self.assertIn("fake-url", output)
        self.assertIn("fake-uuid2", output)
        self.assertIn("fake-url2", output)
        mock_zuul_list_builds.assert_called_once_with(
            "openstack",
            None,
            None,
            set(),
            [],
            None,
            None,
            10,
            None,
            None,
        )

    @mock.patch("logsearch.zuul.API.list_builds")
    def test_query_args_with_repetition(self, mock_zuul_list_builds):
        mock_zuul_list_builds.return_value = [self.build1]

        output = self._run_cli(
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
                "--review",
                "800087",
                "--patchset",
                "3",
            ]
        )

        self.assertIn("fake-uuid", output)
        self.assertIn("fake-date", output)
        self.assertIn("fake-job", output)
        self.assertIn("fake-branch", output)
        mock_zuul_list_builds.assert_called_once_with(
            "openstack",
            "nova",
            "gate",
            {"nova-grenade-multinode", "nova-next"},
            ["master", "stable/wallaby"],
            "FAILURE",
            True,
            pow(10, 10),
            800087,
            3,
        )

    @mock.patch("logsearch.zuul.API.list_builds")
    def test_zuul_api_error(self, mock_zuul_list_builds):
        mock_zuul_list_builds.side_effect = zuul.ZuulException(
            "Cannot access Zuul"
        )

        output = self._run_cli(args=["build"])

        self.assertIn("Cannot access Zuul", output)
        mock_zuul_list_builds.assert_called_once_with(
            "openstack",
            None,
            None,
            set(),
            [],
            None,
            None,
            10,
            None,
            None,
        )

    @mock.patch("logsearch.zuul.API.list_builds")
    def test_with_job_groups(self, mock_zuul_list_builds):
        mock_zuul_list_builds.return_value = [self.build1]
        config = {
            "job-groups": {
                "a-group": ["job1", "job2"],
                "b-group": ["job2", "job3"],
                "c-group": ["job4"],
            }
        }
        output = self._run_cli(
            config=config,
            args=[
                "build",
                "--job",
                "extra-job",
                "--job-group",
                "a-group",
                "--job-group",
                "b-group",
            ],
        )

        self.assertIn("fake-uuid", output)
        self.assertIn("fake-url", output)
        mock_zuul_list_builds.assert_called_once_with(
            "openstack",
            None,
            None,
            {"job1", "job2", "job3", "extra-job"},
            [],
            None,
            None,
            10,
            None,
            None,
        )

    def test_with_job_groups_not_found(self):
        config = {
            "job-groups": {
                "a-group": ["job1", "job2"],
            }
        }
        output = self._run_cli(
            config=config,
            args=[
                "build",
                "--job-group",
                "b-group",
            ],
        )

        self.assertEqual(
            "The requested job group b-group is not defined in the config "
            "files.\n",
            output,
        )

    @mock.patch("logsearch.zuul.API.list_builds")
    def test_with_multiple_config_files(self, mock_zuul_list_builds):
        mock_zuul_list_builds.return_value = [self.build1]
        config1 = {
            "job-groups": {
                "a-group": ["job1", "job2"],
                "c-group": ["job4"],
            }
        }
        config2 = {
            "job-groups": {
                "b-group": ["job2", "job3"],
            }
        }
        config3 = {
            "job-groups": {
                "b-group": ["should not read this config"],
            }
        }
        with collect_stdout() as stdout:
            with tempfile.TemporaryDirectory() as config_dir:
                with open(os.path.join(config_dir, "config1.yaml"), "w") as f:
                    yaml.dump(config1, f)
                with open(os.path.join(config_dir, "config2.conf"), "w") as f:
                    yaml.dump(config2, f)
                # this file should be ignored as it does not have yaml or conf
                # extension
                with open(os.path.join(config_dir, "config3.bak"), "w") as f:
                    yaml.dump(config3, f)
                with tempfile.TemporaryDirectory() as cache_dir:
                    main.main(
                        args=[
                            "--config-dir",
                            config_dir,
                            "--log-store-dir",
                            cache_dir,
                            "build",
                            "--job-group",
                            "a-group",
                            "--job-group",
                            "b-group",
                        ]
                    )
        output = stdout.getvalue()

        self.assertIn("fake-uuid", output)
        self.assertIn("fake-url", output)
        mock_zuul_list_builds.assert_called_once_with(
            "openstack",
            None,
            None,
            {"job1", "job2", "job3"},
            [],
            None,
            None,
            10,
            None,
            None,
        )

    def test_patchset_without_review_error(self):
        output = self._run_cli(args=["build", "--patchset", "1"])
        self.assertIn(
            "The patchset parameter is only valid if the review parameters "
            "is also provided.",
            output,
        )

    @mock.patch("logsearch.zuul.API.list_builds")
    def test_review_and_patchset_makes_unlimited(self, mock_zuul_list_builds):
        self._run_cli(
            args=[
                "build",
                "--review",
                "80086",
                "--patchset",
                "13",
                "--limit",
                "1",
            ]
        )
        mock_zuul_list_builds.assert_called_once_with(
            "openstack",
            None,
            None,
            set(),
            [],
            None,
            None,
            pow(10, 10),
            80086,
            13,
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
                        "--log-store-dir",
                        cache_dir,
                        "build-show",
                        "fake-uuid",
                    ]
                )

        output = stdout.getvalue()
        self.assertIn("fake-uuid", output)
        self.assertIn("fake-url", output)

    @mock.patch("logsearch.zuul.API.get_build")
    def test_not_cached(self, mock_get_build):

        mock_get_build.return_value = self.build1

        output = self._run_cli(args=["build-show", "fake-uuid"])

        self.assertIn("fake-uuid", output)
        self.assertIn("fake-url", output)
        mock_get_build.assert_called_once_with("openstack", "fake-uuid")


class TestLogSearch(TestBase):
    def setUp(self) -> None:
        super(TestLogSearch, self).setUp()

        patcher = mock.patch("logsearch.zuul.API")
        self.addCleanup(patcher.stop)
        self.mock_zuul = patcher.start()
        self.fake_zuul = fakes.FakeZuul()
        self.mock_zuul.return_value = self.fake_zuul

    def test_one_build_default_file(self):
        self.fake_zuul.set_builds([self.build1])
        self.fake_zuul.add_log_content(
            self.build1["uuid"],
            "job-output.txt",
            "foo\n"
            "... some-pattern and bar\n"
            "baz\n"
            "another some-pattern instance\n",
        )

        output = self._run_cli(
            args=[
                "log",
                "some-pattern",
            ]
        )

        self.assertRegex(
            output, "fake-uuid:.*job-output.txt:2:... some-pattern and bar"
        )
        self.assertRegex(
            output,
            "fake-uuid:.*job-output.txt:4:another some-pattern instance",
        )
        self.assertIn("fake-url", output)
        self.assertIn("1/1", output)

    def test_one_build_default_file_no_match(self):
        self.fake_zuul.set_builds([self.build1])
        self.fake_zuul.add_log_content(
            self.build1["uuid"],
            "job-output.txt",
            "foo\n"
            "... some-pattern and bar\n"
            "baz\n"
            "another some-pattern instance\n",
        )

        output = self._run_cli(
            args=[
                "log",
                "non-matching-pattern",
            ]
        )

        self.assertNotIn("pattern", output)
        self.assertIn("fake-uuid", output)
        self.assertIn("fake-url", output)
        self.assertIn("0/1", output)

    def test_multi_build_multi_file(self):
        self.fake_zuul.set_builds([self.build1, self.build2])
        self.fake_zuul.add_log_content(
            self.build1["uuid"],
            "job-output.txt",
            "foo\n"
            "... some-pattern and bar\n"
            "baz\n"
            "another some-pattern instance\n",
        )
        self.fake_zuul.add_log_content(
            self.build1["uuid"], "other-file", "foo"
        )
        self.fake_zuul.add_log_content(
            self.build2["uuid"], "job-output.txt", "nothingness\n"
        )
        self.fake_zuul.add_log_content(
            self.build2["uuid"], "other-file", "some-pattern\n"
        )

        output = self._run_cli(
            args=[
                "log",
                "--file",
                "job-output.txt",
                "--file",
                "other-file",
                "pattern",
            ]
        )

        self.assertRegex(
            output, "fake-uuid:.*job-output.txt:2:... some-pattern and bar"
        )
        self.assertRegex(
            output,
            "fake-uuid:.*job-output.txt:4:another some-pattern instance",
        )
        self.assertNotRegex(output, r"fake-uuid:\w+other-file")
        self.assertNotRegex(output, r"fake-uuid2:\w+job-output.txt")
        self.assertRegex(output, "fake-uuid2:.*other-file:1:some-pattern")
        self.assertIn("fake-url", output)
        self.assertIn("fake-url2", output)
        self.assertIn("2/2", output)

    def test_builds_no_log_url_and_file_missing(self):
        self.fake_zuul.set_builds([self.build1, self.build2])
        self.build1["log_url"] = None
        self.fake_zuul.add_log_content(
            self.build2["uuid"], "job-output.txt", "pattern\n"
        )

        output = self._run_cli(
            args=[
                "log",
                "--file",
                "job-output.txt",
                "--file",
                "non-existent-file",
                "pattern",
            ]
        )

        self.assertIn("fake-uuid: empty log URL. Skipping.", output)
        self.assertIn(
            "fake-uuid2: non-existent-file: \nDownload failed: HTTPError",
            output,
        )
        self.assertRegex(output, "fake-uuid2:.*job-output.txt:1:pattern")
        self.assertIn("1/2", output)

    def test_match_with_context(self):
        self.fake_zuul.set_builds([self.build1])
        self.fake_zuul.add_log_content(
            self.build1["uuid"],
            "file1",
            "before context\n"
            "match\n"
            "after context\n"
            "do not emit\n"
            "before context2\n"
            "match2\n",
        )

        self.fake_zuul.add_log_content(
            self.build1["uuid"],
            "file2",
            "do not emit\n"
            "before context3\n"
            "match3\n"
            "match4\n"
            "after context3\n"
            "do not emit\n",
        )

        output = self._run_cli(
            args=[
                "log",
                "--file",
                "file1",
                "--file",
                "file2",
                "--context",
                "1",
                "match",
            ]
        )

        self.assertIn("before context", output)
        self.assertIn("match", output)
        self.assertIn("after context", output)
        self.assertIn("before context2", output)
        self.assertIn("match2", output)
        self.assertIn("before context3", output)
        self.assertIn("match3", output)
        self.assertIn("match4", output)
        self.assertIn("after context3", output)
        self.assertNotIn("do not emit", output)
        self.assertIn("fake-url", output)
        self.assertIn("1/1", output)

    def test_stored_search_not_found(self):
        config = {
            "searches": {
                "my-search1": {
                    "regex": "some-pattern",
                }
            }
        }
        output = self._run_cli(
            config=config,
            args=[
                "storedsearch",
                "my-search2",
            ],
        )

        self.assertEqual(
            "The stored search my-search2 not found in the configuration. "
            "Available searches ['my-search1'].\n",
            output,
        )

    def test_stored_search_cli_defaults_applied(self):
        self.fake_zuul.set_builds([self.build1])
        self.fake_zuul.add_log_content(
            self.build1["uuid"],
            "job-output.txt",
            "foo\n"
            "... some-pattern and bar\n"
            "baz\n"
            "another some-pattern instance\n",
        )
        config = {
            "searches": {
                "my-search1": {
                    "regex": "some-pattern",
                }
            }
        }
        output = self._run_cli(
            config=config,
            args=[
                "storedsearch",
                "my-search1",
            ],
        )

        # job-output.txt is defaulted
        self.assertRegex(
            output, "fake-uuid:.*job-output.txt:2:... some-pattern and bar"
        )
        self.assertRegex(
            output,
            "fake-uuid:.*job-output.txt:4:another some-pattern instance",
        )
        self.assertIn("fake-url", output)
        self.assertIn("1/1", output)
        self.assertEqual(1, len(self.fake_zuul.list_build_calls))
        # tenant and limit are defaulted
        self.assertEqual(
            ("openstack", None, None, set(), [], None, None, 10, None, None),
            self.fake_zuul.list_build_calls[0],
        )

    def test_stored_search_cli_defaults_overridden_via_config(self):
        self.fake_zuul.set_builds([self.build1])
        self.fake_zuul.add_log_content(
            self.build1["uuid"],
            "job-output2.txt",
            "foo\n"
            "... some-pattern and bar\n"
            "baz\n"
            "another some-pattern instance\n",
        )
        config = {
            "job-groups": {
                "group1": ["job1", "job2"],
            },
            "searches": {
                "my-search1": {
                    "tenant": "my-tenant",
                    "project": "my-project",
                    "files": ["job-output2.txt"],
                    "voting": True,
                    "limit": 11,
                    "job-groups": ["group1"],
                    "regex": "some-pattern",
                }
            },
        }
        output = self._run_cli(
            config=config,
            args=[
                "storedsearch",
                "my-search1",
            ],
        )

        self.assertRegex(
            output, "fake-uuid:.*job-output2.txt:2:... some-pattern and bar"
        )
        self.assertRegex(
            output,
            "fake-uuid:.*job-output2.txt:4:another some-pattern instance",
        )
        self.assertIn("fake-url", output)
        self.assertIn("1/1", output)
        self.assertEqual(
            (
                "my-tenant",
                "my-project",
                None,
                {"job1", "job2"},
                [],
                None,
                True,
                11,
                None,
                None,
            ),
            self.fake_zuul.list_build_calls[0],
        )

    def test_stored_search_undefined_config_value_defined_in_cli(self):
        self.fake_zuul.set_builds([self.build1])
        self.fake_zuul.add_log_content(
            self.build1["uuid"],
            "job-output2.txt",
            "foo\n"
            "... some-pattern and bar\n"
            "baz\n"
            "another some-pattern instance\n",
        )
        config = {
            "job-groups": {
                "group1": ["job1", "job2"],
            },
            "searches": {
                "my-search1": {
                    "project": "my-project",
                    "files": ["job-output2.txt"],
                    "result": "FAILURE",
                    "regex": "some-pattern",
                }
            },
        }

        output = self._run_cli(
            config=config,
            args=[
                "storedsearch",
                # not defined in the config so it can be define
                # in the invocation
                "--limit",
                "13",
                # also not defined in the config so it can be
                # defined here
                "--job-group",
                "group1",
                # defined in the config so it is ignored if
                # provided at the invocation
                "--project",
                "other-project",
                # ditto ignored
                "--file",
                "other-file",
                "my-search1",
            ],
        )

        self.assertRegex(
            output, "fake-uuid:.*job-output2.txt:2:... some-pattern and bar"
        )
        self.assertRegex(
            output,
            "fake-uuid:.*job-output2.txt:4:another some-pattern instance",
        )
        self.assertIn("fake-url", output)
        self.assertIn("1/1", output)
        # other-file is not tried to be accessed
        self.assertNotIn("Download failed:", output)
        # result and limit is overridden via cli, tenant is defaulted, project
        # from cli is ignored
        self.assertEqual(
            (
                "openstack",
                "my-project",
                None,
                {"job1", "job2"},
                [],
                "FAILURE",
                None,
                13,
                None,
                None,
            ),
            self.fake_zuul.list_build_calls[0],
        )

    def test_stored_search_only_jobs_but_no_job_groups_in_config(self):
        self.fake_zuul.set_builds([self.build1])
        self.fake_zuul.add_log_content(
            self.build1["uuid"],
            "job-output.txt",
            "foo\n"
            "... some-pattern and bar\n"
            "baz\n"
            "another some-pattern instance\n",
        )
        config = {
            "searches": {
                "my-search1": {
                    "jobs": ["job3"],
                    "regex": "some-pattern",
                }
            },
        }

        output = self._run_cli(
            config=config,
            args=[
                "storedsearch",
                "my-search1",
            ],
        )

        # job-output.txt is defaulted
        self.assertRegex(
            output, "fake-uuid:.*job-output.txt:2:... some-pattern and bar"
        )
        self.assertRegex(
            output,
            "fake-uuid:.*job-output.txt:4:another some-pattern instance",
        )
        self.assertIn("fake-url", output)
        self.assertIn("1/1", output)
        self.assertEqual(1, len(self.fake_zuul.list_build_calls))
        # tenant and limit are defaulted
        self.assertEqual(
            (
                "openstack",
                None,
                None,
                {"job3"},
                [],
                None,
                None,
                10,
                None,
                None,
            ),
            self.fake_zuul.list_build_calls[0],
        )

    def test_stored_search_both_jobs_and_job_groups_in_config(self):
        self.fake_zuul.set_builds([self.build1])
        self.fake_zuul.add_log_content(
            self.build1["uuid"],
            "job-output.txt",
            "foo\n"
            "... some-pattern and bar\n"
            "baz\n"
            "another some-pattern instance\n",
        )
        config = {
            "job-groups": {
                "group1": ["job1", "job2"],
            },
            "searches": {
                "my-search1": {
                    "job-groups": ["group1"],
                    "jobs": ["job3"],
                    "regex": "some-pattern",
                }
            },
        }
        output = self._run_cli(
            config=config,
            args=[
                "storedsearch",
                "my-search1",
            ],
        )

        # job-output.txt is defaulted
        self.assertRegex(
            output, "fake-uuid:.*job-output.txt:2:... some-pattern and bar"
        )
        self.assertRegex(
            output,
            "fake-uuid:.*job-output.txt:4:another some-pattern instance",
        )
        self.assertIn("fake-url", output)
        self.assertIn("1/1", output)
        self.assertEqual(1, len(self.fake_zuul.list_build_calls))
        # tenant and limit are defaulted
        self.assertEqual(
            (
                "openstack",
                None,
                None,
                {"job1", "job2", "job3"},
                [],
                None,
                None,
                10,
                None,
                None,
            ),
            self.fake_zuul.list_build_calls[0],
        )
