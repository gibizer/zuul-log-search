import argparse
import logging
import re
import sys
import traceback
from typing import Callable

from logsearch import zuul
from logsearch import handlers

LOG = logging.getLogger("__main__")


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
                raise handlers.CmdException(
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
            build_handler=handlers.BuildCmd,
            build_show_handler=handlers.BuildShowCmd,
            logsearch_handler=handlers.LogSearchCmd,
        )
        handler = arg_handler.get_subcommand_handler()
        handler()
    except handlers.CmdException as e:
        print(e)
        LOG.debug(traceback.format_exc())


if __name__ == "__main__":
    main()
