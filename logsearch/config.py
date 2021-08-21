import argparse
import logging
import io
import os
from typing import Dict, List, Set, Optional, Any, Iterable
import yaml


LOG = logging.getLogger(__name__)


class ConfigError(BaseException):
    pass


class PersistentConfig:
    """Configuration read and merged from multiple config files"""

    CONFIG_FILE_EXTENSIONS = [".conf", ".yaml"]

    def __init__(self, config_dir):
        self._job_groups: Dict[str, List[str]] = {}
        self._searches_dict: Dict[str, Dict] = {}
        self._init_from_dir(config_dir)
        self._searches = {
            name: PersistentSearch(name, value, self)
            for name, value in self._searches_dict.items()
        }

    def _init_from_dir(self, config_dir):
        for current_dir, _, files in os.walk(config_dir):
            for file in files:
                if any(
                    file.endswith(ext) for ext in self.CONFIG_FILE_EXTENSIONS
                ):
                    file = os.path.join(current_dir, file)
                    LOG.debug(f"Reading config file {file}")
                    with open(file) as f:
                        config_dict = yaml.safe_load(f)
                        if config_dict:
                            self._init_from_config_dict(config_dict)

    def _init_from_config_dict(self, config_dict: dict) -> None:
        # if there is a key conflict between multiple files then we simply
        # overwrite
        self._job_groups.update(config_dict.get("job-groups", {}))
        self._searches_dict.update(config_dict.get("searches", {}))

    @property
    def job_groups(self) -> Dict[str, List[str]]:
        return self._job_groups

    @property
    def searches(self) -> Dict[str, "PersistentSearch"]:
        return self._searches


def _expand_job_groups(
    requested_groups: Iterable[str], defined_groups: Dict[str, List[str]]
) -> Set[str]:
    jobs: Set[str] = set()
    for job_group in requested_groups:
        if job_group not in defined_groups:
            raise ConfigError(
                f"The requested job group {job_group} is not defined "
                f"in the config files."
            )

        # simply expand the groups to individual jobs
        jobs.update(defined_groups[job_group])
    return jobs


class PersistentSearch:
    def __init__(
        self, name, search_dict: Dict[str, Any], config: PersistentConfig
    ) -> None:
        self._name = name
        self._search = search_dict
        self._config = config

    @property
    def name(self):
        return self._name

    @property
    def jobs(self) -> Set[str]:
        jobs = set(self._search.get("jobs", set()))
        requested_groups = self._search.get("job-groups", set())
        jobs.update(
            _expand_job_groups(requested_groups, self._config.job_groups)
        )
        return jobs

    @property
    def tenant(self) -> Optional[str]:
        return self._search.get("tenant")

    @property
    def project(self) -> Optional[str]:
        return self._search.get("project")

    @property
    def pipeline(self) -> Optional[str]:
        return self._search.get("pipeline")

    @property
    def branches(self) -> List[str]:
        return self._search.get("branches", [])

    @property
    def result(self) -> Optional[str]:
        return self._search.get("result")

    @property
    def voting(self) -> Optional[bool]:
        return self._search.get("voting")

    @property
    def limit(self) -> Optional[int]:
        return self._search.get("limit")

    @property
    def regex(self) -> str:
        if "regex" not in self._search:
            raise ConfigError(
                f"The regex parameter is missing from {self.name} stored "
                f"search, but it is mandatory."
            )
        return self._search["regex"]

    @property
    def before_context(self) -> Optional[int]:
        return self._search.get("before-context")

    @property
    def after_context(self) -> Optional[int]:
        return self._search.get("after-context")

    @property
    def context(self) -> Optional[int]:
        return self._search.get("context")

    @property
    def files(self) -> Set[str]:
        return self._search.get("files", {})

    def to_dict(self) -> Dict:
        return {self._name: self._search}


class NullPersistentSearch(PersistentSearch):
    def __init__(self, config: PersistentConfig):
        super(NullPersistentSearch, self).__init__("null-search", {}, config)

    @property
    def regex(self) -> str:
        return ""


class Config:
    """The arguments of a single command invocation based on the command line
    args and the configuration files"""

    def __init__(self, args: argparse.Namespace) -> None:
        self._args: argparse.Namespace = args
        self._config = PersistentConfig(self._args.config_dir)
        self._jobs: set[str] = set()
        self._requested_search: PersistentSearch = NullPersistentSearch(
            self._config
        )
        self._init_from_args()

    def _init_from_args(self) -> None:
        # calculate jobs from command line and expand requested job groups
        if "jobs" in self._args:
            self._jobs = set(self._args.jobs)

        if "job_groups" in self._args:
            expanded_jobs = _expand_job_groups(
                self._args.job_groups, self._config.job_groups
            )
            self._jobs.update(expanded_jobs)

        if "files" in self._args:
            # ensure that file list has unique elements
            self._args.files = set(self._args.files)
            # if not provided default it
            if not self._args.files:
                self._args.files = {"job-output.txt"}

        if "patchset" in self._args and self._args.patchset:
            if "review_id" not in self._args or not self._args.review_id:
                raise ConfigError(
                    "The patchset parameter is only valid if the review "
                    "parameters is also provided."
                )
            # we want to ignore --limit as --patchset and --review already
            # limits the query but zuul API applies a default limit so we need
            # so set a high number here to not get limited by that.
            self._args.limit = pow(10, 10)

        # A persistent search is requested so we need to load the search
        # config from there.
        if "search" in self._args:
            self._apply_persistent_search_config(self._args.search)

    def _apply_persistent_search_config(self, name):
        search = self._config.searches.get(name)
        if not search:
            raise ConfigError(
                f"The stored search {name} not found in the configuration. "
                f"Available searches {list(self._config.searches.keys())}."
            )
        self._requested_search = search

    @property
    def jobs(self) -> Set[str]:
        return self._requested_search.jobs or self._jobs

    @property
    def tenant(self) -> str:
        return self._requested_search.tenant or self._args.tenant

    @property
    def project(self) -> Optional[str]:
        return self._requested_search.project or self._args.project

    @property
    def pipeline(self) -> Optional[str]:
        return self._requested_search.pipeline or self._args.pipeline

    @property
    def branches(self) -> List[str]:
        return self._requested_search.branches or self._args.branches

    @property
    def result(self) -> Optional[str]:
        return self._requested_search.result or self._args.result

    @property
    def voting(self) -> Optional[bool]:
        if self._requested_search.voting is not None:
            return self._requested_search.voting
        else:
            return self._args.voting

    @property
    def limit(self) -> int:
        return self._requested_search.limit or self._args.limit

    @property
    def regex(self) -> str:
        return self._requested_search.regex or self._args.regex

    @property
    def before_context(self) -> int:
        return (
            self._requested_search.before_context or self._args.before_context
        )

    @property
    def after_context(self) -> int:
        return self._requested_search.after_context or self._args.after_context

    @property
    def context(self) -> int:
        return self._requested_search.context or self._args.context

    @property
    def log_store_dir(self) -> str:
        return self._args.log_store_dir

    @property
    def files(self) -> Set[str]:
        return self._requested_search.files or self._args.files

    @property
    def uuid(self) -> str:
        return self._args.uuid

    @property
    def stored_search_data_yaml(self) -> str:
        config_yaml_stream = io.StringIO()
        yaml.dump(
            self._requested_search.to_dict(),
            config_yaml_stream,
        )
        return config_yaml_stream.getvalue()

    @property
    def review_id(self) -> int:
        return self._args.review_id

    @property
    def patchset(self) -> int:
        return self._args.patchset
