import contextlib
import datetime
import io
import os
import sys
import tempfile
from typing import Generator, Dict, Iterable, Optional
import unittest
from unittest import mock
import yaml

from logsearch import main
from logsearch import search
from logsearch.tests import fakes
from logsearch import zuul
from logsearch import constants


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
            "start_time": "2022-02-09T16:57:33",
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
            "start_time": "2022-02-10T19:35:39",
            "end_time": "fake-date",
            "project": "fake-project",
            "branch": "fake-branch",
            "job_name": "fake-job",
            "pipeline": "fake-pipeline",
            "result": "fake-result",
            "log_url": "fake-log-url",
        }

        # fix the size of the terminal so that the output wrapping is stable
        patcher = mock.patch(
            "shutil.get_terminal_size",
            return_value=os.terminal_size((160, 24)),
        )
        self.addCleanup(patcher.stop)
        patcher.start()

    @staticmethod
    def _run_cli(
        config: Optional[Dict] = None,
        args: Iterable[str] = (),
        cache_dir: Optional[str] = None,
    ) -> str:
        with collect_stdout() as stdout:
            with test_config(config or {}) as config_dir:
                with contextlib.ExitStack() as stack:
                    if not cache_dir:
                        cache_dir = stack.enter_context(
                            tempfile.TemporaryDirectory()
                        )

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
            None,
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
            None,
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
            (
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
                None,
            ),
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
                # not defined in the config so it can be defined in the cli
                # Note that in general --limit and --days should not be mixed
                # but in this test the Zuul logic is mocked so we can easily
                # test that both param can be overridden on the CLI
                "--days",
                "3",
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
                3,
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
                None,
            ),
            self.fake_zuul.list_build_calls[0],
        )

    def test_match(self):
        # no stored search queries for the dev branch so this build will not
        # match any queries
        build_dev_branch = {
            "uuid": "fake-uuid-dev",
            "ref_url": "fake-url",
            "patchset": "1",
            "end_time": "fake-date",
            "project": "fake-project",
            "branch": "dev",
            "job_name": "job1",
            "pipeline": "fake-pipeline",
            "result": "FAILURE",
            "log_url": "fake-log-url",
        }
        # the pattern would match but not the build query
        self.fake_zuul.add_log_content(
            build_dev_branch["uuid"],
            "job-output.txt",
            "pattern1\n" "pattern2\n" "pattern3\n",
        )

        # there will a be stored search that matches the build but there will
        # not be logs matching the stored regex
        build_only_build_match = {
            "uuid": "fake-uuid1",
            "ref_url": "fake-url",
            "patchset": "1",
            "end_time": "fake-date",
            "project": "fake-project",
            "branch": "main",
            "job_name": "job1",
            "pipeline": "fake-pipeline",
            "result": "FAILURE",
            "log_url": "fake-log-url",
        }
        # no pattern match
        self.fake_zuul.add_log_content(
            build_only_build_match["uuid"],
            "job-output.txt",
            "this will not match with anything stored\n",
        )

        # there will be two stored search that matches the build but only one
        # of them will match the regex
        build_two_build_matches_one_log_match = {
            "uuid": "fake-uuid2",
            "ref_url": "fake-url",
            "patchset": "1",
            "end_time": "fake-date",
            "project": "fake-project",
            "branch": "main",
            "job_name": "job2",
            "pipeline": "fake-pipeline",
            "result": "FAILURE",
            "log_url": "fake-log-url",
        }
        # the file content only matches with my-search2
        self.fake_zuul.add_log_content(
            build_two_build_matches_one_log_match["uuid"],
            "job-output.txt",
            "pattern2\n",
        )

        # there will be two stored search that matches the build and both
        # will match the regex too
        build_two_build_and_log_matches = {
            "uuid": "fake-uuid3",
            "ref_url": "fake-url",
            "patchset": "1",
            "end_time": "fake-date",
            "project": "fake-project",
            "branch": "main",
            "job_name": "job2",
            "pipeline": "fake-pipeline",
            "result": "FAILURE",
            "log_url": "fake-log-url",
        }
        # the file content matches with my-search2 and my-search3
        self.fake_zuul.add_log_content(
            build_two_build_and_log_matches["uuid"],
            "job-output.txt",
            "pattern2\n" "pattern3\n",
        )

        self.fake_zuul.set_builds(
            [
                build_dev_branch,
                build_only_build_match,
                build_two_build_matches_one_log_match,
                build_two_build_and_log_matches,
            ]
        )

        config = {
            "searches": {
                # will not match with build some due to build query some due
                # to pattern
                "my-search1": {
                    "jobs": ["job1"],
                    "branches": ["main"],
                    "regex": "pattern1",
                },
                # there will be two hits for this search
                "my-search2": {
                    "jobs": ["job2"],
                    "branches": ["main"],
                    "regex": "pattern2",
                },
                # there will be one hit for this search
                "my-search3": {
                    "jobs": ["job2"],
                    "branches": ["main"],
                    "regex": "pattern3",
                },
            },
        }
        output = self._run_cli(
            config=config,
            args=[
                "match",
                "--result",
                "FAILURE",
            ],
        )

        # build_dev_branch
        self.assertNotRegex(
            output, "fake-uuid-dev: Search .* matched build query"
        )

        # build_only_build_match
        self.assertRegex(
            output, "fake-uuid1: Search my-search1 matched build query"
        )
        self.assertNotRegex(output, "fake-uuid1: Search .* matched signature!")

        # build_two_build_matches_one_log_match
        self.assertRegex(
            output, "fake-uuid2: Search my-search2 matched build query"
        )
        self.assertRegex(
            output, "fake-uuid2: Search my-search3 matched build query"
        )
        self.assertRegex(
            output, "fake-uuid2: Search my-search2 matched signature!"
        )
        self.assertRegex(
            output, "fake-uuid2:.*/fake-uuid2/job-output.txt:1:pattern2"
        )
        self.assertNotRegex(
            output, "fake-uuid2: Search my-search3 matched signature!"
        )

        # build_two_build_and_log_matches
        self.assertRegex(
            output, "fake-uuid3: Search my-search2 matched build query"
        )
        self.assertRegex(
            output, "fake-uuid3: Search my-search3 matched build query"
        )
        self.assertRegex(
            output, "fake-uuid3: Search my-search2 matched signature!"
        )
        self.assertRegex(
            output, "fake-uuid3:.*/fake-uuid3/job-output.txt:1:pattern2"
        )
        self.assertRegex(
            output, "fake-uuid3: Search my-search3 matched signature!"
        )
        self.assertRegex(
            output, "fake-uuid3:.*/fake-uuid3/job-output.txt:2:pattern3"
        )

        # my-search1 never matched to any signature
        self.assertNotRegex(output, ".*: Search my-search1 matched signature!")

        # assert the result table
        self.assertRegex(output, r"fake-uuid-dev .* | \[\]")
        self.assertRegex(output, r"fake-uuid1 .* | \[\]")
        self.assertRegex(output, r"fake-uuid2 .* | \['my-search2'\]")
        self.assertRegex(
            output, r"fake-uuid3 .* | \['my-search2', 'my-search3'\]"
        )

        self.assertEqual(1, len(self.fake_zuul.list_build_calls))
        self.assertEqual(
            (
                "openstack",
                None,
                None,
                set(),
                [],
                "FAILURE",
                None,
                10,
                None,
                None,
                None,
            ),
            self.fake_zuul.list_build_calls[0],
        )


class TestCacheShow(TestBase):
    def test_empty_cache(self):
        output = self._run_cli(args=("cache-show",))

        self.assertRegex(output, r"Disk size.*\| 0.00 B")
        self.assertRegex(output, r"Number of builds.*\| 0")
        self.assertRegex(output, r"Number of logfiles.*\| 0")
        self.assertRegex(output, r"Oldest build.*\| ")

    def test_cache_stats(self):
        patcher = mock.patch("logsearch.zuul.API")
        self.addCleanup(patcher.stop)
        mock_zuul = patcher.start()
        fake_zuul = fakes.FakeZuul()
        mock_zuul.return_value = fake_zuul

        fake_zuul.set_builds([self.build1, self.build2])
        fake_zuul.add_log_content(
            self.build1["uuid"],
            "job-output.txt",
            "foo\n"
            "... some-pattern and bar\n"
            "baz\n"
            "another some-pattern instance\n",
        )
        fake_zuul.add_log_content(self.build1["uuid"], "other-file", "foo")
        fake_zuul.add_log_content(
            self.build2["uuid"], "job-output.txt", "nothingness\n"
        )
        fake_zuul.add_log_content(
            self.build2["uuid"], "other-file", "some-pattern\n"
        )

        with tempfile.TemporaryDirectory() as cache_dir:
            # run a log search to have things in the cache
            self._run_cli(
                cache_dir=cache_dir,
                args=[
                    "log",
                    "--file",
                    "job-output.txt",
                    "--file",
                    "other-file",
                    "pattern",
                ],
            )

            # check the stats of the cache
            output = self._run_cli(cache_dir=cache_dir, args=("cache-show",))

            self.assertRegex(output, r"Disk size.*\| 653.00 B")
            self.assertRegex(output, r"Number of builds.*\| 2")
            self.assertRegex(output, r"Number of logfiles.*\| 4")
            self.assertRegex(output, r"Oldest build.*\| 2022-02-09 16:57:33")


class TestPurgeShow(TestBase):
    def test_empty_cache(self):
        output = self._run_cli(args=("cache-purge", "--gb", "0.001"))

        self.assertRegex(output, r"Disk size.*\| 0.00 B")
        self.assertRegex(output, r"Number of builds.*\| 0")
        self.assertRegex(output, r"Number of logfiles.*\| 0")
        self.assertRegex(output, r"Oldest build.*\| ")

        output = self._run_cli(args=("cache-purge", "--days", "1"))

        self.assertRegex(output, r"Disk size.*\| 0.00 B")
        self.assertRegex(output, r"Number of builds.*\| 0")
        self.assertRegex(output, r"Number of logfiles.*\| 0")
        self.assertRegex(output, r"Oldest build.*\| ")

    def test_by_days(self):
        patcher = mock.patch("logsearch.zuul.API")
        self.addCleanup(patcher.stop)
        mock_zuul = patcher.start()
        fake_zuul = fakes.FakeZuul()
        mock_zuul.return_value = fake_zuul

        fake_zuul.set_builds([self.build1, self.build2])
        fake_zuul.add_log_content(
            self.build1["uuid"],
            "job-output.txt",
            "foo\n"
            "... some-pattern and bar\n"
            "baz\n"
            "another some-pattern instance\n",
        )
        fake_zuul.add_log_content(self.build1["uuid"], "other-file", "foo")
        fake_zuul.add_log_content(
            self.build2["uuid"], "job-output.txt", "nothingness\n"
        )
        fake_zuul.add_log_content(
            self.build2["uuid"], "other-file", "some-pattern\n"
        )

        with tempfile.TemporaryDirectory() as cache_dir:
            # run a log search to have things in the cache
            self._run_cli(
                cache_dir=cache_dir,
                args=[
                    "log",
                    "--file",
                    "job-output.txt",
                    "--file",
                    "other-file",
                    "pattern",
                ],
            )

            # set the current date to the oldest build so this call should
            # keep every build in the cache
            with mock.patch(
                "logsearch.utils.now",
                return_value=datetime.datetime.strptime(
                    self.build1["start_time"], constants.DATETIME_FORMAT
                ),
            ):
                output = self._run_cli(
                    cache_dir=cache_dir, args=("cache-purge", "--days", "1")
                )
                # only want to assert the cache state after the purge
                output = output.split("Purging...", maxsplit=2)[1]

            self.assertRegex(output, r"Disk size.*\| 653.00 B")
            self.assertRegex(output, r"Number of builds.*\| 2")
            self.assertRegex(output, r"Number of logfiles.*\| 4")
            self.assertRegex(output, r"Oldest build.*\| 2022-02-09 16:57:33")

            # now move the current time forward so that the older build is more
            # than a day old. So the next purge call should remove the older
            # build but keep the newer one
            with mock.patch(
                "logsearch.utils.now",
                return_value=datetime.datetime.strptime(
                    self.build1["start_time"], constants.DATETIME_FORMAT
                )
                + datetime.timedelta(days=1, minutes=1),
            ):
                output = self._run_cli(
                    cache_dir=cache_dir, args=("cache-purge", "--days", "1")
                )
                # only want to assert the cache state after the purge
                output = output.split("Purging...", maxsplit=2)[1]

            self.assertRegex(output, r"Disk size.*\| 307.00 B")
            self.assertRegex(output, r"Number of builds.*\| 1")
            self.assertRegex(output, r"Number of logfiles.*\| 2")
            self.assertRegex(output, r"Oldest build.*\| 2022-02-10 19:35:39")

    def test_by_size(self):
        patcher = mock.patch("logsearch.zuul.API")
        self.addCleanup(patcher.stop)
        mock_zuul = patcher.start()
        fake_zuul = fakes.FakeZuul()
        mock_zuul.return_value = fake_zuul

        fake_zuul.set_builds([self.build1, self.build2])
        fake_zuul.add_log_content(
            self.build1["uuid"],
            "job-output.txt",
            "foo\n"
            "... some-pattern and bar\n"
            "baz\n"
            "another some-pattern instance\n",
        )
        fake_zuul.add_log_content(self.build1["uuid"], "other-file", "foo")
        fake_zuul.add_log_content(
            self.build2["uuid"], "job-output.txt", "nothingness\n"
        )
        fake_zuul.add_log_content(
            self.build2["uuid"], "other-file", "some-pattern\n"
        )

        with tempfile.TemporaryDirectory() as cache_dir:
            # run a log search to have things in the cache
            self._run_cli(
                cache_dir=cache_dir,
                args=[
                    "log",
                    "--file",
                    "job-output.txt",
                    "--file",
                    "other-file",
                    "pattern",
                ],
            )

            # purge it down to 100MB, so everyting should remain
            output = self._run_cli(
                cache_dir=cache_dir, args=("cache-purge", "--gb", "0.1")
            )
            # only want to assert the cache state after the purge
            output = output.split("Purging...", maxsplit=2)[1]

            self.assertRegex(output, r"Disk size.*\| 653.00 B")
            self.assertRegex(output, r"Number of builds.*\| 2")
            self.assertRegex(output, r"Number of logfiles.*\| 4")
            self.assertRegex(output, r"Oldest build.*\| 2022-02-09 16:57:33")

            # now purge it down to < 653 bytes but not smaller than 300 so only
            # the oldest build is deleted
            output = self._run_cli(
                cache_dir=cache_dir,
                args=("cache-purge", "--gb", str(600 / 1024 / 1024 / 1024)),
            )
            # only want to assert the cache state after the purge
            output = output.split("Purging...", maxsplit=2)[1]

            self.assertRegex(output, r"Disk size.*\| 307.00 B")
            self.assertRegex(output, r"Number of builds.*\| 1")
            self.assertRegex(output, r"Number of logfiles.*\| 2")
            self.assertRegex(output, r"Oldest build.*\| 2022-02-10 19:35:39")
