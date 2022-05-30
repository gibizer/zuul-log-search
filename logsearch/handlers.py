import argparse
import collections
import logging
import shutil
from typing import List, Dict, Any

import prettytable  # type: ignore

from logsearch import config
from logsearch import search
from logsearch import zuul

LOG = logging.getLogger(__name__)


class BuildTable:
    def __init__(self, build):
        self.build = build

    def __str__(self):
        t = prettytable.PrettyTable()
        t.field_names = ["field", "value"]
        t.add_rows(
            [
                ["uuid", self.build["uuid"]],
                ["finished", self.build["end_time"]],
                ["project", self.build["project"]],
                ["branch", self.build["branch"]],
                ["job", self.build["job_name"]],
                ["pipeline", self.build["pipeline"]],
                ["result", self.build["result"]],
                ["review", self.build["ref_url"]],
                ["patchset", self.build["patchset"]],
                ["log url", self.build["log_url"]],
            ]
        )
        t.align = "l"
        # Constant 5 was determined experimentally with terminal width
        # more or equal 30.
        t.max_table_width = shutil.get_terminal_size().columns - 5
        return t.__str__()


class BuildsTable:
    ARG_TO_FIELD_NAMES = {
        "jobs": "job_name",
        "branches": "branch",
        "review_id": "ref_url",
    }

    DEFAULT_FIELDS = ["uuid", "end_time"]
    FIELD_TO_COLUMN_NAMES = {
        "ref_url": "review",
        "end_time": "finished",
        "job_name": "job",
    }

    def __init__(self, builds: List[Dict], args: config.Config) -> None:
        self.builds = builds
        self.extra_fields = self._get_extra_field_names_from_requested_args(
            args
        )

    def _get_extra_field_names_from_requested_args(
        self, args: config.Config
    ) -> List[str]:
        """Calculate what build fields to show based on the requested args.

        Fields handled by non repeatable args are shown when the user is not
        filtering for a specific value of the field.

        Fields handled by repeatable args are shown when the user is either not
        filtering or filtering for multiple values.
        """
        fields = []
        for arg_name in ["project", "pipeline", "result", "review_id"]:
            if getattr(args, arg_name) is None:
                fields.append(self.ARG_TO_FIELD_NAMES.get(arg_name, arg_name))

        for arg_name in ["branches", "jobs"]:
            value = getattr(args, arg_name)
            if len(value) == 0 or len(value) > 1:
                fields.append(self.ARG_TO_FIELD_NAMES.get(arg_name, arg_name))

        return fields

    def __str__(self) -> str:
        t = prettytable.PrettyTable()
        for field_name in self.DEFAULT_FIELDS + self.extra_fields:
            t.add_column(
                self.FIELD_TO_COLUMN_NAMES.get(field_name, field_name), []
            )

        for build in self.builds:
            row = []
            for field_name in self.DEFAULT_FIELDS + self.extra_fields:
                row.append(build.get(field_name))
            t.add_row(row)
        t.align = "l"
        # Constant 5 was determined experimentally with terminal width
        # more or equal 30.
        t.max_table_width = shutil.get_terminal_size().columns - 5
        return t.__str__()


class BuildsWithSignaturesTable(BuildsTable):
    def __init__(
        self,
        builds: List[Dict],
        args: config.Config,
        build_uuids_to_search_names: Dict[str, List[str]],
    ) -> None:
        super(BuildsWithSignaturesTable, self).__init__(builds, args)
        # extend the table with an extra column
        self.FIELD_TO_COLUMN_NAMES["matching_searches"] = "matching searches"
        # extend the builds with the extra field to show in that column
        for build in builds:
            build["matching_searches"] = build_uuids_to_search_names[
                build["uuid"]
            ]
        # make the new column visible
        self.extra_fields.append("matching_searches")


class CacheStatsTable:
    def __init__(self, stats: search.BuildLogCache.Stats):
        self.stats = stats

    @staticmethod
    def _format_bytes(_bytes):
        power = 2**10
        n = 0
        units = {0: "B", 1: "KB", 2: "MB", 3: "GB", 4: "TB"}
        while _bytes > power:
            _bytes /= power
            n += 1
        return f"{_bytes:.2f} {units[n]}"

    def __str__(self):
        t = prettytable.PrettyTable()
        t.title = "Cache statistics"
        t.header = False
        t.add_rows(
            [
                ["Disk size", self._format_bytes(self.stats.size)],
                ["Number of builds", self.stats.builds],
                ["Number of logfiles", self.stats.logfiles],
                [
                    "Oldest build",
                    self.stats.oldest_build if self.stats.builds else "",
                ],
            ]
        )
        t.align = "l"
        # Constant 5 was determined experimentally with terminal width
        # more or equal 30.
        t.max_table_width = shutil.get_terminal_size().columns - 5
        return t.__str__()


class CmdException(Exception):
    def __init__(self, msg):
        self.msg = msg
        super().__init__(msg)

    def __str__(self):
        return self.msg


class Cmd:
    def __init__(self, zuul_api: zuul.API) -> None:
        self.zuul_api = zuul_api
        self.config: config.Config

    def configure(self, args: argparse.Namespace) -> "Cmd":
        # This is catch 22 if we want to get debug info from config parsing
        # the we cannot use config object here
        if args.debug:
            logging.basicConfig(level=logging.DEBUG)

        self.config = config.Config(args)
        return self

    def execute(self) -> None:
        raise NotImplementedError()


class BuildShowCmd(Cmd):
    def execute(self) -> None:
        cache = search.BuildLogCache(self.config.log_store_dir, self.zuul_api)
        try:
            build = cache.get_build_metadata(self.config.uuid)
        except FileNotFoundError:
            build = self.zuul_api.get_build(
                self.config.tenant, self.config.uuid
            )
        print(BuildTable(build))


class BuildCmd(Cmd):
    def execute(self) -> None:
        builds = self.zuul_api.list_builds(
            self.config.tenant,
            self.config.project,
            self.config.pipeline,
            self.config.jobs,
            self.config.branches,
            self.config.result,
            self.config.voting,
            self.config.limit,
            self.config.review_id,
            self.config.patchset,
            self.config.days_ago,
        )
        print(BuildsTable(builds, self.config))


class LogSearchCmd(Cmd):
    def __init__(self, zuul_api: zuul.API) -> None:
        super().__init__(zuul_api)
        self.ls = search.MultiRegexLogSearch()

    def _search_logs(self, build_uuid_to_build, build_uuid_to_files, builds):
        matching_builds = []
        for build_uuid in build_uuid_to_files.keys():
            lines = self.ls.get_matches(
                build_uuid_to_files[build_uuid],
                self.config.regex,
                self.config.before_context,
                self.config.after_context,
                self.config.context,
            )
            for line in lines:
                print(f"{build_uuid}:{line}")
            if lines:
                matching_builds.append(build_uuid_to_build[build_uuid])
                print()
        return matching_builds

    def _download_logs_for_builds(self, builds):
        cache = search.BuildLogCache(self.config.log_store_dir, self.zuul_api)
        build_uuid_to_build = {build["uuid"]: build for build in builds}
        build_uuid_to_files = collections.defaultdict(set)
        for build in builds:
            if not build["log_url"]:
                print(f"{build['uuid']}: empty log URL. Skipping.")
                continue

            for file in self.config.files:
                # if the download fails the the result is None, skip searching
                # those files
                local_path = cache.ensure_build_log_file(build, file)
                if local_path:
                    build_uuid_to_files[build["uuid"]].add(local_path)
        return build_uuid_to_build, build_uuid_to_files

    def _get_builds(self) -> List[Dict[str, Any]]:
        builds = self.zuul_api.list_builds(
            self.config.tenant,
            self.config.project,
            self.config.pipeline,
            self.config.jobs,
            self.config.branches,
            self.config.result,
            self.config.voting,
            self.config.limit,
            self.config.review_id,
            self.config.patchset,
            self.config.days_ago,
        )
        return builds

    def execute(self) -> None:
        builds = self._get_builds()
        print("Found builds:")
        print(BuildsTable(builds, self.config))

        print("Downloading logs:")
        (
            build_uuid_to_build,
            build_uuid_to_files,
        ) = self._download_logs_for_builds(builds)

        print("Searching logs:")
        matching_builds = self._search_logs(
            build_uuid_to_build, build_uuid_to_files, builds
        )
        print(
            f"Builds with matching logs {len(matching_builds)}/{len(builds)}:"
        )
        print(BuildsTable(matching_builds, self.config))


# NOTE(gibi): A stored search is just a logsearch with different
# source of config. The Config object internally handles the
# loading transparently. So the same search logic can be applied.
class StoredSearchCmd(LogSearchCmd):
    def __init__(self, zuul_api: zuul.API) -> None:
        super().__init__(zuul_api)

    def configure(self, args: argparse.Namespace) -> "StoredSearchCmd":
        super().configure(args)
        print("Running stored search:")
        print(
            "\n".join(
                [
                    "  " + line
                    for line in self.config.stored_search_data_yaml.split("\n")
                ]
            )
        )
        return self


class MatchCmd(LogSearchCmd):
    @staticmethod
    def _build_satisfies_stored_search(
        build: Dict, stored_search_config: config.PersistentSearch
    ) -> bool:
        return (
            (
                not stored_search_config.jobs
                or build["job_name"] in stored_search_config.jobs
            )
            and (
                not stored_search_config.project
                or build["project"] == stored_search_config.project
            )
            and (
                not stored_search_config.pipeline
                or build["pipeline"] == stored_search_config.pipeline
            )
            and (
                not stored_search_config.branches
                or build["branch"] in stored_search_config.branches
            )
            and (
                not stored_search_config.result
                or build["result"] == stored_search_config.result
            )
            and (
                stored_search_config.voting is None
                or build["voting"] == stored_search_config.voting
            )
        )

    def execute(self) -> None:
        # intentionally not calling super().execute() as we need an extended
        # logic but reusing pieces from the parent.
        builds = self._get_builds()
        print("Found builds to match:")
        print(BuildsTable(builds, self.config))

        build_uuid_to_stored_search_names = collections.defaultdict(list)
        for build in builds:
            print(f"Matching stored searches for build {build['uuid']}")
            for (
                name,
                psearch,
            ) in self.config.persistent_config.searches.items():
                # 1) we have to check if the given build data satisfies the
                # build query part of the stored search.
                if not self._build_satisfies_stored_search(build, psearch):
                    LOG.debug(f"{name} build query doesn't match. skip.")
                    continue
                print(f"{build['uuid']}: Search {name} matched build query.")

                # 2) then we override the cli config with the given persistent
                # search and download the logs based on the resulting query
                # NOTE(gibi): applying the next persistent search simply remove
                # removes the previously applied persistent search so we
                # dont need a cleanup step at the end of the core of this loop.
                self.config.apply_persistent_search_config(name)
                (
                    build_uuid_to_build,
                    build_uuid_to_files,
                ) = self._download_logs_for_builds([build])

                # 3) then run the search in the logs and see if it results in
                # any matching lines
                matching_builds = self._search_logs(
                    build_uuid_to_build, build_uuid_to_files, [build]
                )

                if matching_builds:
                    print(f"{build['uuid']}: Search {name} matched signature!")
                    build_uuid_to_stored_search_names[build["uuid"]].append(
                        name
                    )
                else:
                    print()
            print()

        # 4) print the collected results in a single table
        # remove the last applied persistent search not to interfere with the
        # columns in the result table
        self.config.remove_applied_persistent_search_config()
        print(
            BuildsWithSignaturesTable(
                builds, self.config, build_uuid_to_stored_search_names
            )
        )


class CacheShowCmd(Cmd):
    def execute(self) -> None:
        cache = search.BuildLogCache(self.config.log_store_dir, self.zuul_api)
        print(CacheStatsTable(cache.get_stats()))


class CachePurgeCmd(Cmd):
    def execute(self) -> None:
        cache = search.BuildLogCache(self.config.log_store_dir, self.zuul_api)
        print(CacheStatsTable(cache.get_stats()))
        print("Purging...")
        cache.purge(
            days_to_keep=self.config.days_to_keep,
            max_size_gb=self.config.gb_to_keep,
        )
        print(CacheStatsTable(cache.get_stats()))
