import logging
from typing import List, Dict, Optional, Set
import os

import requests

LOG = logging.getLogger(__name__)


class ZuulException(BaseException):
    pass


class API:
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
        tenant,
        project: Optional[str],
        pipeline: Optional[str],
        jobs: Set[str],
        branches: List[str],
        result: Optional[str],
        voting: Optional[bool],
        limit: Optional[int],
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
