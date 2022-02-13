import datetime
import logging
import math
from typing import List, Dict, Optional, Set
import os

import requests

LOG = logging.getLogger(__name__)


class ZuulException(BaseException):
    pass


class API:

    # 2022-02-06T12:21:04
    DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S"

    def __init__(self, zuul_url: str) -> None:
        self.zuul_url = zuul_url

    def get_build(self, tenant: str, build_uuid: str) -> Dict:
        try:
            r = requests.get(
                self.zuul_url + f"/tenant/{tenant}/builds",
                params={"uuid": build_uuid},
            )
            r.raise_for_status()
            builds = r.json()
            if len(builds) == 0:
                raise ZuulException(f"Build {build_uuid} not found")
            if len(builds) > 1:
                raise ZuulException(
                    f"More than one results for {build_uuid}: %s" % builds
                )
            return builds[0]
        except requests.RequestException as e:
            raise ZuulException("Cannot access Zuul") from e

    def list_builds(
        self,
        tenant: str,
        project: Optional[str],
        pipeline: Optional[str],
        jobs: Set[str],
        branches: List[str],
        result: Optional[str],
        voting: Optional[bool],
        limit: Optional[int],
        change: Optional[int],
        patchset: Optional[int],
        days_ago: Optional[int],
    ) -> List[Dict]:
        params: Dict = {}
        if project is not None:
            params["project"] = project
        if pipeline is not None:
            params["pipeline"] = pipeline
        params["job_name"] = jobs
        params["branch"] = branches
        if result is not None:
            params["result"] = result
        if voting is not None:
            params["voting"] = "1" if voting else "0"
        if limit is not None:
            params["limit"] = limit
        if change is not None:
            params["change"] = change
        if patchset is not None:
            params["patchset"] = patchset

        if days_ago is None:
            return self.call_zuul(tenant, params)

        # days-ago type query is not supported by zuul out of the box.
        # So we simulate that here with multiple queries to find the proper
        # limit that match the requested date.
        return self.call_zuul_with_days_ago(tenant, params, days_ago)

    def _get_build_start_date(self, build: dict):
        return datetime.datetime.strptime(
            build["start_time"], self.DATETIME_FORMAT
        )

    def _now(self):
        # needs to wrap it, so we can mock in during test
        return datetime.datetime.now()

    def call_zuul_with_days_ago(
        self, tenant: str, params: dict, days_ago: int
    ) -> List[Dict]:
        one_day_in_sec = datetime.timedelta(days=1).total_seconds()
        now = self._now()
        target_start_date = now - datetime.timedelta(days=days_ago)

        original_limit = params.get("limit", 10)

        while True:
            # we assume that the list is ordered by start_time by the API,
            # so the earliest build is the last
            builds = self.call_zuul(tenant, params)
            earliest_build = builds[-1]
            earliest_date = self._get_build_start_date(earliest_build)
            # it is the number of days we see in the current set of builds
            time_window = (
                now - earliest_date
            ).total_seconds() / one_day_in_sec

            if time_window < days_ago:
                # we need from builds from zuul

                # This is our heuristic of the number of builds in the
                # requested time window.
                new_limit = math.ceil(days_ago / time_window * params["limit"])

                # Avoid too small steps towards the target limit when we are
                # close. It is better to overestimate the limit and then filter
                # too old results locally than underestimate and take an
                # excessive amount of Zuul queries with slowly increasing
                # limits.
                increase = max(original_limit, new_limit - params["limit"])
                params["limit"] += increase
            else:
                # we have more we need
                break

        # so we have more than enough builds lets collect the not too old
        # builds
        builds = [
            build
            for build in builds
            if self._get_build_start_date(build) >= target_start_date
        ]

        return builds

    def call_zuul(self, tenant: str, params: dict) -> List[Dict]:
        try:
            r = requests.get(
                self.zuul_url + f"/tenant/{tenant}/builds", params=params
            )
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            raise ZuulException("Cannot access Zuul") from e

    @staticmethod
    def fetch_log(build, log_file, local_path, progress_handler) -> None:
        url = os.path.join(build["log_url"], log_file)
        LOG.debug(f"Fetching {url}")
        i = 0
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            with open(local_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=10 * 1024):
                    f.write(chunk)
                    i += 1
                    progress_handler(i)
