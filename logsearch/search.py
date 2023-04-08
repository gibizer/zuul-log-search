import contextlib
import dataclasses
import datetime
import json
import logging
import shutil
import os
from typing import List, Dict, Optional, Set

import requests.exceptions
import ripgrepy  # type: ignore

from logsearch import zuul
from logsearch import constants
from logsearch import utils


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

    @dataclasses.dataclass
    class Stats:
        oldest_build: datetime.datetime = datetime.datetime.now()
        size: int = 0
        builds: int = 0
        logfiles: int = 0

        @classmethod
        def collect(cls, cache_dir) -> "BuildLogCache.Stats":
            stats = cls()
            # the first level is one directory per build
            with os.scandir(cache_dir) as it:
                for build_dir in it:
                    stats._update_from_build_dir(build_dir)

            return stats

        def _update_from_build_dir(self, build_dir):
            self.builds += 1
            # each build has a build.meta file that is not counted as a
            # logfile
            self.logfiles -= 1
            # each build directory has its own directory hierarchy with
            # log files
            for root, dirs, files in os.walk(build_dir):
                self.logfiles += len(files)
                self.size += sum(
                    os.path.getsize(os.path.join(root, file)) for file in files
                )
                self._update_oldest_build(root, files)

        def _update_oldest_build(self, root, files):
            if "build.meta" not in files:
                return

            with open(os.path.join(root, "build.meta"), "r") as f:
                build = json.load(f)
                start_time = datetime.datetime.strptime(
                    build["start_time"], constants.DATETIME_FORMAT
                )
                self.oldest_build = min(self.oldest_build, start_time)

    def get_stats(self) -> Stats:
        return self.Stats.collect(self.base_dir)

    def get_size(self, build):
        size = 0
        for root, dirs, files in os.walk(
            os.path.join(self.base_dir, build["uuid"])
        ):
            size += sum(
                os.path.getsize(os.path.join(root, file)) for file in files
            )
        return size

    def get_build_uuids(self):
        # the first level is one directory per build
        it = os.scandir(self.base_dir)
        return (os.path.basename(build_dir) for build_dir in it)

    def get_build_metas(self):
        return (
            self.get_build_metadata(build_uuid)
            for build_uuid in self.get_build_uuids()
        )

    def purge(
        self,
        days_to_keep: Optional[int] = None,
        max_size_gb: Optional[float] = None,
    ):
        # enforced by the arg parser already
        assert bool(days_to_keep) ^ bool(max_size_gb)
        target_start_date: Optional[datetime.datetime] = None
        if days_to_keep:
            target_start_date = utils.now() - datetime.timedelta(
                days=days_to_keep
            )
            LOG.debug(f"Target start date for kept builds {target_start_date}")

        max_size_bytes = 0
        if max_size_gb:
            max_size_bytes = int(max_size_gb * 1024 * 1024 * 1024)

        builds_in_cache = self.get_build_metas()
        # let's sort backwards in time
        builds_in_cache = sorted(
            builds_in_cache,
            key=lambda build: datetime.datetime.strptime(
                build["start_time"], constants.DATETIME_FORMAT
            ),
            reverse=True,
        )

        # find the last build we can keep
        size_sum = 0
        start_to_delete = 0
        for idx, build in enumerate(builds_in_cache):
            size = self.get_size(build)
            start_date = datetime.datetime.strptime(
                build["start_time"], constants.DATETIME_FORMAT
            )

            if target_start_date and start_date < target_start_date:
                break

            if max_size_bytes and size_sum + size > max_size_bytes:
                break

            # we can keep the current build
            start_to_delete = idx + 1
            size_sum += size

        # then delete the rest
        num_to_delete = len(builds_in_cache[start_to_delete:])
        for idx, build in enumerate(builds_in_cache[start_to_delete:]):
            LOG.debug(f'Deleting build {build["uuid"]}')
            print(f"\rDeleting {num_to_delete}/{idx + 1}", end="")
            shutil.rmtree(os.path.join(self.base_dir, build["uuid"]))
        if num_to_delete:
            print()


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
