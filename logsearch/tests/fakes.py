import collections
from typing import List, Optional, Dict, Any

from logsearch import zuul


class FakeZuul(zuul.API):
    def __init__(self) -> None:
        super().__init__("fake_zuul_url")
        self.builds: List[Dict[str, Any]] = []
        self.log_content: Dict[str, Any] = collections.defaultdict(
            lambda: collections.defaultdict(str)
        )
        self.fetched_files: List[str] = []

    def add_build(self, build):
        self.builds.append(build)

    def set_builds(self, builds):
        self.builds = builds

    def add_log_content(self, build_uuid, log_file_name, content):
        self.log_content[build_uuid][log_file_name] = content

    def fetch_log(self, build, log_file, local_path, progress_handler):
        with open(local_path, "w") as f:
            f.write(self.log_content[build["uuid"]][log_file])
        self.fetched_files.append(log_file)

    def list_builds(
        self,
        tenant,
        project: Optional[str],
        pipeline: Optional[str],
        jobs: List[str],
        branches: List[str],
        result: Optional[str],
        voting: Optional[bool],
        limit: Optional[int],
    ) -> List[Dict]:
        return self.builds
