import logging
from typing import List, Dict
import os
from urllib.request import urlretrieve

import requests

LOG = logging.getLogger(__name__)


class API:
    def __init__(self, zuul_url: str) -> None:
        self.zuul_url = zuul_url

    def list_builds(
        self,
        tenant,
        project=None,
        pipeline=None,
        job=None,
        branch=None,
        result=None,
        voting=None,
        limit=None,
    ) -> List[Dict]:
        params = {}
        if project is not None:
            params["project"] = project
        if pipeline is not None:
            params["pipeline"] = pipeline
        if job is not None:
            params["job_name"] = job
        if branch is not None:
            params["branch"] = branch
        if result is not None:
            params["result"] = result
        if voting is not None:
            params["voting"] = "1" if voting else "0"
        if limit is not None:
            params["limit"] = limit

        r = requests.get(
            self.zuul_url + f"/tenant/{tenant}/builds", params=params
        )
        r.raise_for_status()
        return r.json()

    @staticmethod
    def fetch_log(build, log_file, local_path, progress_handler) -> None:
        url = os.path.join(build["log_url"], log_file)
        urlretrieve(url=url, filename=local_path, reporthook=progress_handler)
