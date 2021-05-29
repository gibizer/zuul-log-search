import unittest
from unittest import mock

import responses

from logsearch import zuul


class TestZuulAPI(unittest.TestCase):
    @responses.activate
    def test_list_builds(self):
        api = zuul.API(zuul_url="http://fake_url")

        responses.add(
            responses.GET,
            "http://fake_url/tenant/sentinel.tenant/builds",
            json={},
            status=200,
        )

        api.list_builds(tenant=mock.sentinel.tenant)

        self.assertTrue(
            responses.assert_call_count(
                "http://fake_url/tenant/sentinel.tenant/builds", 1
            )
        )
