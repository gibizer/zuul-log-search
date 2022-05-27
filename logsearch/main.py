import argparse
import logging
import re
import sys
import traceback
from typing import Callable, Optional
import os

from logsearch import config
from logsearch import handlers
from logsearch import zuul

LOG = logging.getLogger("__main__")


class ArgHandler:
    def __init__(
        self,
        build_handler,
        build_show_handler,
        logsearch_handler,
        stored_search_handler,
        match_handler,
        cache_show_handler,
        cache_purge_handler,
    ) -> None:
        self.build_handler = build_handler
        self.build_show_handler = build_show_handler
        self.logsearch_handler = logsearch_handler
        self.stored_search_handler = stored_search_handler
        self.match_handler = match_handler
        self.cache_show_handler = cache_show_handler
        self.cache_purge_handler = cache_purge_handler

    @staticmethod
    def _add_build_filter_args(arg_parser: argparse.ArgumentParser) -> None:
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
            "--job-group",
            dest="job_groups",
            default=[],
            action="append",
            help="The name of a job group defined in the configuration. The "
            "jobs in the group will be use in the same way as if you "
            "specified them one by one with --job. Can be repeated.",
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
        arg_parser.add_argument(
            "--review",
            type=int,
            dest="review_id",
            help="The number from the gerrit URL of a review.",
        )
        arg_parser.add_argument(
            "--patchset",
            type=int,
            dest="patchset",
            help="The patchset number. Only valid if --review is also used "
            "and makes --limit ignored.",
        )
        arg_parser.add_argument(
            "--days",
            type=int,
            default=None,
            dest="days_ago",
            help="It limits the result to the last N days of builds. If "
            "provided it makes --limit ignored.",
        )

    def _add_logsearch_filter_args(
        self, argparser: argparse.ArgumentParser
    ) -> None:
        argparser.add_argument(
            "--file",
            dest="files",
            default=[],
            action="append",
            help="A relative filepath within the build directory to search "
            "in. Can be repeated. Defaulted to job-output.txt",
        )
        argparser.add_argument(
            "-B",
            "--before-context",
            help="Print number of lines of leading context before matching"
            "lines",
        )
        argparser.add_argument(
            "-A",
            "--after-context",
            help="Print number of lines of trailing context after matching"
            "lines",
        )
        argparser.add_argument(
            "-C",
            "--context",
            help="Print number of context lines",
        )

    def _parse_args(self, sys_args) -> argparse.Namespace:
        arg_parser = argparse.ArgumentParser(usage="Search Zuul CI results")
        arg_parser.add_argument(
            "--debug",
            dest="debug",
            default=False,
            action="store_true",
            help="Print debug logs",
        )
        arg_parser.add_argument(
            "--zuul-api-url",
            type=str,
            default="https://zuul.opendev.org/api",
            help="The API url of the Zuul deployment to use. "
            "Defaulted to the OpenDev Zuul (https://zuul.opendev.org/api)",
        )
        arg_parser.add_argument(
            "--log-store-dir",
            dest="log_store_dir",
            default=".logsearch/",
            help="The local directory to download the logs to. "
            "Defaulted to .logsearch/",
        )

        def config_dir_location(value: Optional[str]) -> str:
            if value:
                return value

            if os.path.exists(".logsearch.conf.d/"):
                return ".logsearch.conf.d/"

            base = os.getenv(
                "XDG_CONFIG_HOME", default=os.path.expanduser("~/.config")
            )
            return os.path.join(base, "logsearch")

        arg_parser.add_argument(
            "--config-dir",
            dest="config_dir",
            # NOTE(gibi): None value cannot be used as that is not triggering
            # the type() call
            default="",
            type=config_dir_location,
            help="The local directory storing config files and stored "
            "queries. If not provided then the tool checks the following "
            "locations in order. It uses .logsearch.conf.d/ in the current "
            "directory if exists. Otherwise, uses $XDG_CONFIG_HOME/logsearch/ "
            "if XDG_CONFIG_HOME is defined. Otherwise, uses "
            "~/.config/logsearch/.",
        )
        arg_parser.add_argument(
            "--tenant",
            type=str,
            default="openstack",
            help="The name of the tenant in the Zuul installation. "
            "Defaulted to 'openstack'",
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
            )
            .configure(args)
            .execute()
        )

        build_parser = subparsers.add_parser(
            "build",
            help="Search for builds",
        )
        self._add_build_filter_args(build_parser)
        build_parser.set_defaults(
            func=lambda args: self.build_handler(zuul.API(args.zuul_api_url))
            .configure(args)
            .execute()
        )

        log_parser = subparsers.add_parser(
            "log",
            help="Search the logs of the builds",
        )
        self._add_build_filter_args(log_parser)
        self._add_logsearch_filter_args(log_parser)

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
            )
            .configure(args)
            .execute()
        )

        stored_search_parser = subparsers.add_parser(
            "storedsearch",
            help="Run a search defined in the configuration.\n\n"
            "The command line args can be used to fine tune the stored search "
            "where the configuration does not specify a given parameter. If a "
            "parameter is specified by the stored search then the "
            "corresponding command line parameter will be ignored.",
        )
        self._add_build_filter_args(stored_search_parser)
        self._add_logsearch_filter_args(stored_search_parser)
        stored_search_parser.add_argument(
            "search",
            help="The name of the predefined search in the configuration",
            type=str,
        )
        stored_search_parser.set_defaults(
            func=lambda args: self.stored_search_handler(
                zuul.API(args.zuul_api_url)
            )
            .configure(args)
            .execute()
        )

        match_parser = subparsers.add_parser(
            "match", help="Match builds with stored searches.\n\n"
        )
        self._add_build_filter_args(match_parser)
        match_parser.set_defaults(
            func=lambda args: self.match_handler(zuul.API(args.zuul_api_url))
            .configure(args)
            .execute()
        )

        cache_show_parser = subparsers.add_parser(
            "cache-show", help="Show information of the local build cache.\n\n"
        )
        cache_show_parser.set_defaults(
            func=lambda args: self.cache_show_handler(
                zuul.API(args.zuul_api_url)
            )
            .configure(args)
            .execute()
        )

        cache_purge_parser = subparsers.add_parser(
            "cache-purge", help="Reduce the size of the local build cache.\n\n"
        )
        group = cache_purge_parser.add_mutually_exclusive_group(required=True)
        group.add_argument(
            "--days",
            type=int,
            dest="days_to_keep",
            help="Keep the last N days of builds in the local cache.",
        )
        group.add_argument(
            "--gb",
            dest="gb_to_keep",
            type=float,
            help="Reduce the size of the local cache to N.M GB by keeping the "
            "latest builds.",
        )
        cache_purge_parser.set_defaults(
            func=lambda args: self.cache_purge_handler(
                zuul.API(args.zuul_api_url)
            )
            .configure(args)
            .execute()
        )

        return arg_parser.parse_args(args=sys_args)

    def get_subcommand_handler(self, sys_args) -> Callable:
        args = self._parse_args(sys_args)
        return lambda: args.func(args)


def main(args=tuple(sys.argv[1:])) -> None:
    try:
        arg_handler = ArgHandler(
            build_handler=handlers.BuildCmd,
            build_show_handler=handlers.BuildShowCmd,
            logsearch_handler=handlers.LogSearchCmd,
            stored_search_handler=handlers.StoredSearchCmd,
            match_handler=handlers.MatchCmd,
            cache_show_handler=handlers.CacheShowCmd,
            cache_purge_handler=handlers.CachePurgeCmd,
        )
        handler = arg_handler.get_subcommand_handler(args)
        handler()
    except (
        handlers.CmdException,
        config.ConfigError,
        zuul.ZuulException,
    ) as e:
        print(e)
        LOG.debug(traceback.format_exc())


if __name__ == "__main__":
    main()
