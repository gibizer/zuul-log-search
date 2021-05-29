import argparse
import logging
from typing import List, Dict

import prettytable  # type: ignore

from logsearch import zuul
from logsearch import search


class BuildsTable:
    def __init__(self, builds: List[Dict]) -> None:
        self.builds = builds

    def __str__(self) -> str:
        t = prettytable.PrettyTable()
        t.field_names = ["uuid", "finished", "job", "result", "review"]
        for build in self.builds:
            t.add_row(
                [
                    build["uuid"],
                    build["end_time"],
                    build["job_name"],
                    build["result"],
                    build["ref_url"],
                ]
            )
        t.align = "l"
        return t.__str__()


class Cmd:
    def __init__(self, zuul_api: zuul.API) -> None:
        self.zuul_api = zuul_api

    def execute(self, args: argparse.Namespace) -> None:
        if args.debug:
            logging.basicConfig(level=logging.DEBUG)


class BuildCmd(Cmd):
    def execute(self, args: argparse.Namespace) -> None:
        super().execute(args)
        builds = self.zuul_api.list_builds(
            args.tenant,
            args.project,
            args.pipeline,
            args.job,
            args.branch,
            args.result,
            args.voting,
            args.limit,
        )
        print(BuildsTable(builds))


class LogSearchCmd(Cmd):
    def execute(self, args: argparse.Namespace) -> None:
        super().execute(args)
        builds = self.zuul_api.list_builds(
            args.tenant,
            args.project,
            args.pipeline,
            args.job,
            args.branch,
            args.result,
            args.voting,
            args.limit,
        )
        print("Found matching builds:")
        print(BuildsTable(builds))
        print("Downloading logs:")
        cache = search.BuildLogCache(args.log_store_dir, self.zuul_api)
        for build in builds:
            cache.ensure_build_log_file(build, args.file)

        print("Searching logs:")
        ls = search.LogSearch(cache)
        for build in builds:
            matches = ls.get_matches(build, args.file, args.regex)
            for match in ls.get_matches(build, args.file, args.regex):
                print(
                    f"{build['uuid']}:"
                    f"{match['data']['line_number']}:"
                    f"{match['data']['lines']['text'].rstrip()}"
                )
            if matches:
                print()


class ArgHandler:
    def __init__(self, build_handler, logsearch_handler) -> None:
        self.build_handler = build_handler
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
            type=str,
            help="The name of Zuul job run the build",
        )
        arg_parser.add_argument(
            "--branch",
            type=str,
            help="The name of the git branch the build run on",
        )
        arg_parser.add_argument(
            "--result",
            type=str,
            help="The result of the build."
            "E.g. SUCCESS, FAILURE, POST_FAILURE, TIMED_OUT",
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
            default="job-output.txt",
            help="A relative filepath within the build directory to search in."
            "Defaulted to ./job-output.txt",
        )
        log_parser.add_argument(
            "regex", help="A regular expression to search for."
        )
        log_parser.set_defaults(
            func=lambda args: self.logsearch_handler(
                zuul.API(args.zuul_api_url)
            ).execute(args)
        )

        return arg_parser.parse_args()

    def handle_subcommand(self) -> None:
        args = self._parse_args()
        return args.func(args)


def main() -> None:
    ArgHandler(
        build_handler=BuildCmd,
        logsearch_handler=LogSearchCmd,
    ).handle_subcommand()


if __name__ == "__main__":
    main()
