import collections
from typing import List, Optional, Dict, Any, Set

import requests

from logsearch import zuul


class FakeZuul(zuul.API):
    def __init__(self) -> None:
        super().__init__("fake_zuul_url")
        self.builds: List[Dict[str, Any]] = []
        self.log_content: Dict[str, Any] = collections.defaultdict(
            lambda: collections.defaultdict(str)
        )
        self.fetched_files: List[str] = []
        self.list_build_calls: List[tuple] = []

    def add_build(self, build):
        self.builds.append(build)

    def set_builds(self, builds):
        self.builds = builds

    def add_log_content(self, build_uuid, log_file_name, content):
        self.log_content[build_uuid][log_file_name] = content

    def fetch_log(self, build, log_file, local_path, progress_handler):
        self.fetched_files.append(log_file)
        with open(local_path, "w") as f:
            if log_file in self.log_content[build["uuid"]]:
                f.write(self.log_content[build["uuid"]][log_file])
            else:
                raise requests.HTTPError()

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
        change: Optional[int],
    ) -> List[Dict]:
        self.list_build_calls.append(
            (
                tenant,
                project,
                pipeline,
                jobs,
                branches,
                result,
                voting,
                limit,
                change,
            )
        )
        return self.builds
