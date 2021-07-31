import argparse
import logging
import io
import os
from typing import Dict, List, Set, Optional
import yaml


LOG = logging.getLogger(__name__)


class ConfigError(BaseException):
    pass


class PersistentConfig:
    """Configuration read and merged from multiple config files"""

    CONFIG_FILE_EXTENSIONS = [".conf", ".yaml"]

    def __init__(self, config_dir):
        self._job_groups: Dict[str, List[str]] = {}
        self._searches: Dict[str, Dict] = {}
        self._init_from_dir(config_dir)

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
        self._searches.update(config_dict.get("searches", {}))

    @property
    def job_groups(self) -> Dict[str, List[str]]:
        return self._job_groups

    @property
    def searches(self) -> Dict[str, Dict]:
        return self._searches


class Config:
    """The arguments of a single command invocation based on the command line
    args and the configuration files"""

    def __init__(self, args: argparse.Namespace) -> None:
        self._args: argparse.Namespace = args
        self._config = PersistentConfig(self._args.config_dir)
        self._jobs: set[str] = set()
        self._persistent_search_config: Optional[dict] = None
        self._init_from_args()

    def _expand_job_groups(self, requested_groups):
        jobs = set()
        for job_group in requested_groups:
            if job_group not in self._config.job_groups:
                raise ConfigError(
                    f"The requested job group {job_group} is not defined "
                    f"in the config files."
                )

            # simply expand the groups to individual jobs
            jobs.update(self._config.job_groups[job_group])
        return jobs

    def _init_from_args(self) -> None:
        # calculate jobs from command line and expand requested job groups
        if "jobs" in self._args:
            self._jobs = set(self._args.jobs)

        if "job_groups" in self._args:
            expanded_jobs = self._expand_job_groups(self._args.job_groups)
            self._jobs.update(expanded_jobs)

        if "files" in self._args:
            # ensure that file list has unique elements
            self._args.files = set(self._args.files)
            # if not provided default it
            if not self._args.files:
                self._args.files = {"job-output.txt"}

        # A persistent search is requested so we need to load the search
        # config from there.
        if "search" in self._args:
            # This will overwrite config stored in _args
            self._apply_persistent_search_config(self._args.search)

    def _apply_persistent_search_config(self, name):
        search = self._config.searches.get(name)
        if not search:
            raise ConfigError(
                f"The stored search {name} not found in the configuration. "
                f"Available searches {list(self._config.searches.keys())}."
            )
        self._persistent_search_config = search

    def _get_persistent_search_config(self, name, default=None):
        if not self._persistent_search_config:
            return default
        return self._persistent_search_config.get(name, default)

    @property
    def jobs(self) -> Set[str]:
        p_jobs = (
            set(self._get_persistent_search_config("jobs", set())) or set()
        )
        p_job_groups = self._get_persistent_search_config("job-groups", set())
        if p_jobs or p_job_groups:
            p_jobs.update(self._expand_job_groups(p_job_groups))
            return p_jobs

        return self._jobs

    @property
    def tenant(self) -> str:
        p_config = self._get_persistent_search_config("tenant")
        if p_config:
            return p_config
        return self._args.tenant

    @property
    def project(self) -> Optional[str]:
        p_config = self._get_persistent_search_config("project")
        if p_config:
            return p_config
        return self._args.project

    @property
    def pipeline(self) -> Optional[str]:
        p_config = self._get_persistent_search_config("pipeline")
        if p_config:
            return p_config
        return self._args.pipeline

    @property
    def branches(self) -> List[str]:
        p_config = self._get_persistent_search_config("branches")
        if p_config:
            return p_config
        return self._args.branches

    @property
    def result(self) -> Optional[str]:
        p_config = self._get_persistent_search_config("result")
        if p_config:
            return p_config
        return self._args.result

    @property
    def voting(self) -> Optional[bool]:
        p_config = self._get_persistent_search_config("voting")
        if p_config:
            return p_config
        return self._args.voting

    @property
    def limit(self) -> int:
        p_config = self._get_persistent_search_config("limit")
        if p_config:
            return p_config
        return self._args.limit

    @property
    def regex(self) -> str:
        p_config = self._get_persistent_search_config("regex")
        if p_config:
            return p_config
        return self._args.regex

    @property
    def before_context(self) -> int:
        p_config = self._get_persistent_search_config("before-context")
        if p_config:
            return p_config
        return self._args.before_context

    @property
    def after_context(self) -> int:
        p_config = self._get_persistent_search_config("after-context")
        if p_config:
            return p_config
        return self._args.after_context

    @property
    def context(self) -> int:
        p_config = self._get_persistent_search_config("context")
        if p_config:
            return p_config
        return self._args.context

    @property
    def log_store_dir(self) -> str:
        return self._args.log_store_dir

    @property
    def files(self) -> Set[str]:
        p_config = self._get_persistent_search_config("files")
        if p_config:
            return p_config
        return self._args.files

    @property
    def uuid(self) -> str:
        return self._args.uuid

    @property
    def stored_search_data_yaml(self) -> str:
        config_yaml_stream = io.StringIO()
        yaml.dump(
            {self._args.search: self._persistent_search_config},
            config_yaml_stream,
        )
        return config_yaml_stream.getvalue()

    @property
    def review_id(self) -> int:
        return self._args.review_id
