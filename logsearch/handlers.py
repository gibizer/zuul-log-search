import argparse
import collections
import logging
from typing import List, Dict, Any

import prettytable  # type: ignore

from logsearch import config
from logsearch import search
from logsearch import zuul


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
        )
        print(BuildsTable(builds, self.config))


class LogSearchCmd(Cmd):
    def __init__(self, zuul_api: zuul.API) -> None:
        super().__init__(zuul_api)
        self.ls = search.LogSearch()

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
