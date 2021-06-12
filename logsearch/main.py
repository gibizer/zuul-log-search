import argparse
import collections
import logging
import re
import traceback
from typing import List, Dict, Callable

import prettytable  # type: ignore

from logsearch import zuul
from logsearch import search


LOG = logging.getLogger("__main__")


class CmdException(Exception):
    def __init__(self, msg):
        self.msg = msg
        super().__init__(msg)

    def __str__(self):
        return self.msg


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
                [
                    "review",
                    self.build["ref_url"] + "/" + self.build["patchset"],
                ],
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
                if field_name == "ref_url":
                    row.append(build["ref_url"] + "/" + build["patchset"])
                else:
                    row.append(build.get(field_name))
            t.add_row(row)
        t.align = "l"
        return t.__str__()


class Cmd:
    def __init__(self, zuul_api: zuul.API) -> None:
        self.zuul_api = zuul_api

    def execute(self, args: argparse.Namespace) -> None:
        if args.debug:
            logging.basicConfig(level=logging.DEBUG)


class BuildShowCmd(Cmd):
    def execute(self, args: argparse.Namespace) -> None:
        super().execute(args)
        cache = search.BuildLogCache(args.log_store_dir, self.zuul_api)
        try:
            build = cache.get_build_metadata(args.uuid)
        except FileNotFoundError as e:
            raise CmdException(f"Build {args.uuid} is not cached.") from e
        print(BuildTable(build))


class BuildCmd(Cmd):
    def execute(self, args: argparse.Namespace) -> None:
        super().execute(args)
        builds = self.zuul_api.list_builds(
            args.tenant,
            args.project,
            args.pipeline,
            args.jobs,
            args.branches,
            args.result,
            args.voting,
            args.limit,
        )
        print(BuildsTable(builds, args))


class LogSearchCmd(Cmd):
    def execute(self, args: argparse.Namespace) -> None:
        super().execute(args)
        # ensure that file list has unique elements
        args.files = set(args.files)
        # if not provided default it
        if not args.files:
            args.files = {"job-output.txt"}
        builds = self.zuul_api.list_builds(
            args.tenant,
            args.project,
            args.pipeline,
            args.jobs,
            args.branches,
            args.result,
            args.voting,
            args.limit,
        )
        print("Found builds:")
        print(BuildsTable(builds, args))

        print("Downloading logs:")
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

        print("Searching logs:")
        ls = search.LogSearch()
        matching_builds = []
        for build_uuid in build_uuid_to_files.keys():
            lines = ls.get_matches(
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

        print(
            f"Builds with matching logs {len(matching_builds)}/{len(builds)}:"
        )
        print(BuildsTable(matching_builds, args))


class ArgHandler:
    def __init__(
        self, build_handler, build_show_handler, logsearch_handler
    ) -> None:
        self.build_handler = build_handler
        self.build_show_handler = build_show_handler
        self.logsearch_handler = logsearch_handler

    @staticmethod
    def _add_build_filter_args(arg_parser: argparse.ArgumentParser) -> None:
        arg_parser.add_argument(
            "--tenant",
            type=str,
            default="openstack",
            help="The name of the tenant in the Zuul installation. "
            "Defaulted to 'openstack'",
        )
        arg_parser.add_argument(
            "--project",
            type=str,
            help="The name of the project built",
        )
        arg_parser.add_argument(
            "--pipeline",
            type=str,
            help="The name of the Zuul pipeline the build run",
        )
        arg_parser.add_argument(
            "--job",
            dest="jobs",
            default=[],
            action="append",
            help="The name of Zuul job run the build. "
            "Can be repeated to express OR relationship.",
        )
        arg_parser.add_argument(
            "--branch",
            dest="branches",
            default=[],
            action="append",
            help="The name of the git branch the build run on. "
            "Can be repeated to express OR relationship.",
        )
        arg_parser.add_argument(
            "--result",
            type=str,
            choices=[
                "SUCCESS",
                "FAILURE",
                "POST_FAILURE",
                "TIMED_OUT",
                "LOST",
            ],
            help="The result of the build.",
        )
        arg_parser.add_argument(
            "--voting",
            dest="voting",
            default=None,
            action="store_true",
            help="Filter for voting jobs",
        )
        arg_parser.add_argument(
            "--non-voting",
            dest="voting",
            default=None,
            action="store_false",
            help="Filter for non voting jobs",
        )
        arg_parser.add_argument(
            "--limit",
            type=int,
            default=10,
            help="Number of builds returned. Defaulted to 10",
        )

    def _parse_args(self) -> argparse.Namespace:
        arg_parser = argparse.ArgumentParser(usage="Search Zuul CI results")
        arg_parser.add_argument(
            "--debug",
            dest="debug",
            default=False,
            action="store_true",
            help="Print debug logs",
        )
        arg_parser.add_argument(
            "--zuul_api_url",
            type=str,
            default="https://zuul.opendev.org/api",
            help="The API url of the Zuul deployment to use. "
            "Defaulted to the OpenDev Zuul (https://zuul.opendev.org/api)",
        )
        arg_parser.add_argument(
            "--log_store_dir",
            dest="log_store_dir",
            default=".logsearch/",
            help="The local directory to download the logs to. "
            "Defaulted to .logsearch",
        )
        # calling without subcommand prints the help
        arg_parser.set_defaults(func=lambda args: arg_parser.print_help())

        subparsers = arg_parser.add_subparsers()

        build_show_parser = subparsers.add_parser(
            "build-show",
            help="Show the metadata of a specific build",
        )
        build_show_parser.add_argument(
            "uuid",
            type=str,
            help="The UUID of the build",
        )
        build_show_parser.set_defaults(
            func=lambda args: self.build_show_handler(
                zuul.API(args.zuul_api_url)
            ).execute(args)
        )

        build_parser = subparsers.add_parser(
            "build",
            help="Search for builds",
        )
        self._add_build_filter_args(build_parser)
        build_parser.set_defaults(
            func=lambda args: self.build_handler(
                zuul.API(args.zuul_api_url)
            ).execute(args)
        )

        log_parser = subparsers.add_parser(
            "log",
            help="Search the logs of the builds",
        )
        self._add_build_filter_args(log_parser)
        log_parser.add_argument(
            "--file",
            dest="files",
            default=[],
            action="append",
            help="A relative filepath within the build directory to search "
            "in. Can be repeated. Defaulted to job-output.txt",
        )
        log_parser.add_argument(
            "-B",
            "--before-context",
            help="Print number of lines of leading context before matching"
            "lines",
        )
        log_parser.add_argument(
            "-A",
            "--after-context",
            help="Print number of lines of trailing context after matching"
            "lines",
        )
        log_parser.add_argument(
            "-C",
            "--context",
            help="Print number of context lines",
        )

        def regex(value):
            try:
                re.compile(value)
            except re.error as e:
                raise CmdException(
                    f"Invalid regex: '{value}'; " + str(e)
                ) from e
            return value

        log_parser.add_argument(
            "regex",
            help="A regular expression to search for.",
            type=regex,
        )
        log_parser.set_defaults(
            func=lambda args: self.logsearch_handler(
                zuul.API(args.zuul_api_url)
            ).execute(args)
        )

        return arg_parser.parse_args()

    def get_subcommand_handler(self) -> Callable:
        args = self._parse_args()
        return lambda: args.func(args)


def main() -> None:
    try:
        arg_handler = ArgHandler(
            build_handler=BuildCmd,
            build_show_handler=BuildShowCmd,
            logsearch_handler=LogSearchCmd,
        )
        handler = arg_handler.get_subcommand_handler()
        handler()
    except CmdException as e:
        print(e)
        LOG.debug(traceback.format_exc())


if __name__ == "__main__":
    main()
