import tempfile
import unittest
from unittest import mock

import requests

from logsearch import zuul


class TestZuulAPI(unittest.TestCase):
    @mock.patch("requests.get")
    def test_list_builds(self, mock_get):
        mock_rsp = mock.Mock(spec=requests.Response)
        mock_rsp.json.return_value = mock.sentinel.json_rsp
        mock_get.return_value = mock_rsp

        api = zuul.API(zuul_url="https://fake_url")

        result = api.list_builds(
            tenant=mock.sentinel.tenant,
            project=None,
            pipeline=None,
            branches=[],
            jobs=[],
            result=None,
            limit=None,
            voting=None,
        )

        self.assertEqual(mock.sentinel.json_rsp, result)
        mock_get.assert_called_once_with(
            "https://fake_url/tenant/sentinel.tenant/builds",
            params={
                "job_name": [],
                "branch": [],
            },
        )
        mock_rsp.json.assert_called_once_with()
        mock_rsp.raise_for_status.assert_called_once_with()

    @mock.patch("requests.get")
    def test_list_builds_args(self, mock_get):
        mock_rsp = mock.Mock(spec=requests.Response)
        mock_rsp.json.return_value = mock.sentinel.json_rsp
        mock_get.return_value = mock_rsp

        api = zuul.API(zuul_url="https://fake_url")

        api.list_builds(
            tenant="a_tenant",
            project="a_project",
            pipeline="a_pipeline",
            branches=["a_branch", "b_branch"],
            jobs=["a_job", "b_job"],
            result="a_result",
            limit=10,
            voting=True,
        )

        mock_get.assert_called_once_with(
            "https://fake_url/tenant/a_tenant/builds",
            params={
                "project": "a_project",
                "pipeline": "a_pipeline",
                "job_name": ["a_job", "b_job"],
                "branch": ["a_branch", "b_branch"],
                "result": "a_result",
                "voting": "1",
                "limit": 10,
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
