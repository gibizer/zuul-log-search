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
    }

    DEFAULT_FIELDS = ["uuid", "end_time", "ref_url"]
    FIELD_TO_COLUMN_NAMES = {
        "ref_url": "review",
        "end_time": "finished",
        "job_name": "job",
    }

    def __init__(self, builds: List[Dict], args: argparse.Namespace) -> None:
        self.builds = builds
        self.extra_fields = self._get_extra_field_names_from_requested_args(
            args
        )

    def _get_extra_field_names_from_requested_args(
        self, args: argparse.Namespace
    ) -> List[str]:
        """Calculate what build fields to show based on the requested args.

        Fields handled by non repeatable args are shown when the user is not
        filtering for a specific value of the field.

        Fields handled by repeatable args are shown when the user is either not
        filtering or filtering for multiple values.
        """
        fields = []
        for arg_name in ["project", "pipeline", "result"]:
            if getattr(args, arg_name) is None:
                fields.append(self.ARG_TO_FIELD_NAMES.get(arg_name, arg_name))

        for arg_name in ["branches", "jobs"]:
            value = getattr(args, arg_name)
            if value == [] or len(value) > 1:
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

    def execute(self, args: argparse.Namespace) -> None:
        if args.debug:
            logging.basicConfig(level=logging.DEBUG)

        self.config = config.Config(args)


class BuildShowCmd(Cmd):
    def execute(self, args: argparse.Namespace) -> None:
        super().execute(args)
        cache = search.BuildLogCache(args.log_store_dir, self.zuul_api)
        try:
            build = cache.get_build_metadata(args.uuid)
        except FileNotFoundError:
            build = self.zuul_api.get_build(args.tenant, args.uuid)
        print(BuildTable(build))


class BuildCmd(Cmd):
    def execute(self, args: argparse.Namespace) -> None:
        super().execute(args)
        # TODO(gibi): move all the args access to Config
        builds = self.zuul_api.list_builds(
            args.tenant,
            args.project,
            args.pipeline,
            self.config.jobs,
            args.branches,
            args.result,
            args.voting,
            args.limit,
        )
        print(BuildsTable(builds, args))


class LogSearchCmd(Cmd):
    def __init__(self, zuul_api: zuul.API) -> None:
        super().__init__(zuul_api)
        self.ls = search.LogSearch()

    def _search_logs(
        self, args, build_uuid_to_build, build_uuid_to_files, builds
    ):
        matching_builds = []
        for build_uuid in build_uuid_to_files.keys():
            lines = self.ls.get_matches(
                build_uuid_to_files[build_uuid],
                args.regex,
                args.before_context,
                args.after_context,
                args.context,
            )
            for line in lines:
                print(f"{build_uuid}:{line}")
            if lines:
                matching_builds.append(build_uuid_to_build[build_uuid])
                print()
        return matching_builds

    def _download_logs_for_builds(self, args, builds):
        cache = search.BuildLogCache(args.log_store_dir, self.zuul_api)
        build_uuid_to_build = {build["uuid"]: build for build in builds}
        build_uuid_to_files = collections.defaultdict(set)
        for build in builds:
            if not build["log_url"]:
                print(f"{build['uuid']}: empty log URL. Skipping.")
                continue

            for file in args.files:
                # if the download fails the the result is None, skip searching
                # those files
                local_path = cache.ensure_build_log_file(build, file)
                if local_path:
                    build_uuid_to_files[build["uuid"]].add(local_path)
        return build_uuid_to_build, build_uuid_to_files

    def _get_builds(self, args) -> List[Dict[str, Any]]:
        # TODO(gibi): move all the args access to Config
        builds = self.zuul_api.list_builds(
            args.tenant,
            args.project,
            args.pipeline,
            self.config.jobs,
            args.branches,
            args.result,
            args.voting,
            args.limit,
        )
        return builds

    def execute(self, args: argparse.Namespace) -> None:
        super().execute(args)
        # ensure that file list has unique elements
        args.files = set(args.files)
        # if not provided default it
        if not args.files:
            args.files = {"job-output.txt"}

        builds = self._get_builds(args)
        print("Found builds:")
        print(BuildsTable(builds, args))

        print("Downloading logs:")
        (
            build_uuid_to_build,
            build_uuid_to_files,
        ) = self._download_logs_for_builds(args, builds)

        print("Searching logs:")
        matching_builds = self._search_logs(
            args, build_uuid_to_build, build_uuid_to_files, builds
        )
        print(
            f"Builds with matching logs {len(matching_builds)}/{len(builds)}:"
        )
        print(BuildsTable(matching_builds, args))
