import contextlib
import json
import logging
import os
from typing import List, Dict, Optional, Set

import requests.exceptions
import ripgrepy  # type: ignore

from logsearch import zuul


LOG = logging.getLogger(__name__)


class BuildLogCache:
    def __init__(self, log_cache_dir: str, zuul_api: zuul.API) -> None:
        self.base_dir = log_cache_dir
        self.zuul_api = zuul_api
        if not os.path.exists(self.base_dir):
            os.makedirs(self.base_dir)

    def _get_local_path(self, build_uuid: str, file_path: str) -> str:
        return os.path.join(self.base_dir, build_uuid, file_path)

    def _cache_build_meta(self, build: Dict) -> None:
        """Stores a information of the build in a file in the cache"""
        path = self._get_local_path(build["uuid"], "build.meta")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        # simply update if exists
        with open(path, "w") as f:
            json.dump(build, f)

    def ensure_build_log_file(
        self, build: Dict, rel_path_to_log_file: str
    ) -> Optional[str]:
        """Checks if the log exists in the cache and if not downloads it"""

        self._cache_build_meta(build)

        def report_progress(block_number):
            print("\rDownloading", block_number, " ", end="")

        local_path = self._get_local_path(build["uuid"], rel_path_to_log_file)
        if not os.path.exists(local_path):
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            print(f"{build['uuid']}: {rel_path_to_log_file}: ")
            try:
                self.zuul_api.fetch_log(
                    build, rel_path_to_log_file, local_path, report_progress
                )
                print("Done")
            except requests.exceptions.RequestException as e:
                msg = "Download failed: "
                if e.response is not None:
                    msg += f"HTTP {e.response.status_code}"
                else:
                    msg += e.__class__.__name__
                print(msg)
                LOG.debug(f"Fetching log failed: {e}")
                return None

        return local_path

    def get_build_metadata(self, build_uuid):
        path = self._get_local_path(build_uuid, "build.meta")
        with open(path, "r") as f:
            build = json.load(f)
        return build


class LogSearch:
    @contextlib.contextmanager
    def _silence_log(self):
        old_level = logging.getLogger("root").getEffectiveLevel()
        logging.getLogger("root").setLevel(logging.INFO)
        yield
        logging.getLogger("root").setLevel(old_level)

    def get_matches(
        self,
        local_paths: Set[str],
        regexp: str,
        before_context: Optional[int],
        after_context: Optional[int],
        context: Optional[int],
    ) -> List[str]:
        # ripgrepy is very noisy on debug level and unfortunately using the
        # root logger
        with self._silence_log():
            # TODO(gibi): Change Ripgrepy to support multiple paths naturally
            rg = ripgrepy.Ripgrepy(regexp, " ".join(local_paths))
            rg.line_number()
            if before_context:
                rg.before_context(before_context)
            if after_context:
                rg.after_context(after_context)
            if context:
                rg.context(context)
            rg.no_heading()
            rg.with_filename()
            result = rg.run()
            lines = result.as_string.splitlines()
        return lines
