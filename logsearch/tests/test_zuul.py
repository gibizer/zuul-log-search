import copy
import datetime
import tempfile
import unittest
from unittest import mock
from typing import List, Dict

import requests

from logsearch import zuul


class CopyingMock(mock.MagicMock):
    def __call__(self, /, *args, **kwargs):
        args = copy.deepcopy(args)
        kwargs = copy.deepcopy(kwargs)
        return super().__call__(*args, **kwargs)


EMPTY_RESULT: List[Dict] = [{}]


class TestZuulAPI(unittest.TestCase):
    @mock.patch("requests.get")
    def test_list_builds(self, mock_get):
        mock_rsp = mock.Mock(spec=requests.Response)
        mock_rsp.json.return_value = EMPTY_RESULT
        mock_get.return_value = mock_rsp

        api = zuul.API(zuul_url="https://fake_url")

        result = api.list_builds(
            tenant=mock.sentinel.tenant,
            project=None,
            pipeline=None,
            branches=[],
            jobs=set(),
            result=None,
            limit=None,
            voting=None,
            change=None,
            patchset=None,
            days_ago=None,
        )

        self.assertEqual(EMPTY_RESULT, result)
        mock_get.assert_called_once_with(
            "https://fake_url/tenant/sentinel.tenant/builds",
            params={
                "job_name": set(),
                "branch": [],
            },
        )
        mock_rsp.json.assert_called_once_with()
        mock_rsp.raise_for_status.assert_called_once_with()

    @mock.patch("requests.get")
    def test_list_builds_args(self, mock_get):
        mock_rsp = mock.Mock(spec=requests.Response)
        mock_rsp.json.return_value = EMPTY_RESULT
        mock_get.return_value = mock_rsp

        api = zuul.API(zuul_url="https://fake_url")

        api.list_builds(
            tenant="a_tenant",
            project="a_project",
            pipeline="a_pipeline",
            branches=["a_branch", "b_branch"],
            jobs={"a_job", "b_job"},
            result="a_result",
            limit=10,
            voting=True,
            change=803082,
            patchset=2,
            days_ago=None,
        )

        mock_get.assert_called_once_with(
            "https://fake_url/tenant/a_tenant/builds",
            params={
                "project": "a_project",
                "pipeline": "a_pipeline",
                "job_name": {"a_job", "b_job"},
                "branch": ["a_branch", "b_branch"],
                "result": "a_result",
                "voting": "1",
                "limit": 10,
                "change": 803082,
                "patchset": 2,
            },
        )
        mock_rsp.json.assert_called_once_with()
        mock_rsp.raise_for_status.assert_called_once_with()

    @mock.patch("requests.get")
    def test_fetch_log(self, mock_get):
        api = zuul.API(zuul_url="https://fake_url")
        build = {"log_url": "https://fake_log_url"}

        with tempfile.NamedTemporaryFile() as f:
            api.fetch_log(
                build,
                "controller/n-cpu.log",
                f.name,
                mock.sentinel.progress_handler,
            )

        mock_get.assert_called_once_with(
            "https://fake_log_url/controller/n-cpu.log", stream=True
        )


class TestZuulAPIDaysAgo(unittest.TestCase):
    @mock.patch("logsearch.utils.now")
    @mock.patch("logsearch.zuul.API.call_zuul")
    def test_list_builds_with_days_ago_first_zuul_call_is_enough(
        self, mock_call_zuul, mock_now
    ):
        # so we ask for the last 3 days of builds before 2022-02-12T13:00:00
        mock_now.return_value = datetime.datetime(
            year=2022, month=2, day=12, hour=13
        )

        days_ago = 3
        # and zuul has one build for each day the first three is within limit
        # the fourth is 57 minutes older than 3 days
        builds = [
            {"start_time": "2022-02-12T12:03:03"},
            {"start_time": "2022-02-11T12:03:03"},
            {"start_time": "2022-02-10T12:03:03"},
            {"start_time": "2022-02-09T12:03:03"},
        ]
        # we set up the zuul query to use 4 as the initial limit of the query
        start_limit = 4
        # this is already more than what we need to so there won't be any
        # extra call to zuul.
        mock_call_zuul.return_value = builds

        api = zuul.API(zuul_url="https://fake_url")

        builds = api.list_builds(
            tenant="a_tenant",
            project=None,
            pipeline=None,
            branches=[],
            jobs=set(),
            result=None,
            limit=start_limit,
            voting=None,
            change=None,
            patchset=None,
            days_ago=days_ago,
        )

        # we expect that the result is filtered down to the builds in the time
        # window
        self.assertEqual(builds[:3], builds)

        # we expect a single call to zuul with the starting limit
        mock_call_zuul.assert_called_once_with(
            "a_tenant", {"job_name": set(), "branch": [], "limit": 4}
        )

    @mock.patch("logsearch.utils.now")
    # call_zuul takes a mutable dict as arg, so we need to record the call args
    # as deep copies
    @mock.patch("logsearch.zuul.API.call_zuul", new_callable=CopyingMock)
    def test_list_builds_with_days_ago_multiple_calls(
        self, mock_call_zuul, mock_now
    ):
        # so we ask for the last 3 days of builds before 2022-02-12T13:00:00
        mock_now.return_value = datetime.datetime(
            year=2022, month=2, day=12, hour=13
        )
        days_ago = 3
        # and zuul has one build for each day the first three is within limit
        # the third is 57 minutes older than 3 days
        builds = [
            {"start_time": "2022-02-12T12:03:03"},
            {"start_time": "2022-02-11T12:03:03"},
            {"start_time": "2022-02-10T12:03:03"},
            {"start_time": "2022-02-09T12:03:03"},
        ]
        # we set up the logic to start with querying 2 builds
        start_limit = 2
        # so the first call will return the 2 builds. This is not enough, so
        # we expect another zuul calls.
        mock_call_zuul.side_effect = [
            builds[:2],
            builds,
        ]
        api = zuul.API(zuul_url="https://fake_url")

        builds = api.list_builds(
            tenant="a_tenant",
            project=None,
            pipeline=None,
            branches=[],
            jobs=set(),
            result=None,
            limit=start_limit,
            voting=None,
            change=None,
            patchset=None,
            days_ago=days_ago,
        )

        # we expect that the result is filtered down to the builds in the time
        # window
        self.assertEqual(builds[:3], builds)
        # we expect two calls, the second with increased limit
        mock_call_zuul.assert_has_calls(
            [
                mock.call(
                    "a_tenant", {"job_name": set(), "branch": [], "limit": 2}
                ),
                mock.call(
                    "a_tenant", {"job_name": set(), "branch": [], "limit": 6}
                ),
            ]
        )


class TestZuulAPINormalizers(unittest.TestCase):
    @mock.patch("requests.get")
    def test_list_build_ref_url_normalization(self, mock_get):
        mock_rsp = mock.Mock(spec=requests.Response)
        mock_rsp.json.return_value = [
            {"ref_url": "https://opendev.org/openstack/neutron/commit/None"}
        ]
        mock_get.return_value = mock_rsp

        api = zuul.API(zuul_url="https://fake_url")

        result = api.list_builds(
            tenant=mock.sentinel.tenant,
            project="openstack/neutron",
            pipeline="periodic",
            branches=[],
            jobs=set(),
            result=None,
            limit=None,
            voting=None,
            change=None,
            patchset=None,
            days_ago=None,
        )

        self.assertEqual([{"ref_url": None}], result)
        mock_get.assert_called_once_with(
            "https://fake_url/tenant/sentinel.tenant/builds",
            params={
                "project": "openstack/neutron",
                "pipeline": "periodic",
                "job_name": set(),
                "branch": [],
            },
        )
        mock_rsp.json.assert_called_once_with()
        mock_rsp.raise_for_status.assert_called_once_with()

    @mock.patch("requests.get")
    def test_get_build_ref_url_normalization(self, mock_get):
        mock_rsp = mock.Mock(spec=requests.Response)
        mock_rsp.json.return_value = [
            {"ref_url": "https://opendev.org/openstack/neutron/commit/None"}
        ]
        mock_get.return_value = mock_rsp

        api = zuul.API(zuul_url="https://fake_url")

        result = api.get_build(
            tenant=mock.sentinel.tenant,
            build_uuid="53d0f6d71d514992a3b44a9caa5b901f",
        )

        self.assertEqual({"ref_url": None}, result)
        mock_get.assert_called_once_with(
            "https://fake_url/tenant/sentinel.tenant/builds",
            params={
                "uuid": "53d0f6d71d514992a3b44a9caa5b901f",
            },
        )
        mock_rsp.json.assert_called_once_with()
        mock_rsp.raise_for_status.assert_called_once_with()
