import argparse
import logging
import os
from typing import Dict, List, Set, Optional
import yaml


LOG = logging.getLogger(__name__)


class ConfigError(BaseException):
    pass


class PersistentConfig:
    """Configuration read and merged from multiple config files"""

    def __init__(self, config_dir):
        self._job_groups: Dict[str, List[str]] = {}
        self._init_from_dir(config_dir)

    def _init_from_dir(self, config_dir):
        for current_dir, _, files in os.walk(config_dir):
            for file in files:
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

    @property
    def job_groups(self) -> Dict[str, List[str]]:
        return self._job_groups


class Config:
    """The arguments of a single command invocation based on the command line
    args and the configuration files"""

    def __init__(self, args: argparse.Namespace) -> None:
        self._args: argparse.Namespace = args
        self._config = PersistentConfig(self._args.config_dir)
        self._jobs: set[str] = set()
        self._init_from_args()

    def _init_from_args(self) -> None:
        # calculate jobs from command line and expand requested job groups
        if "jobs" in self._args:
            self._jobs = set(self._args.jobs)
            for job_group in self._args.job_groups:
                if job_group not in self._config.job_groups:
                    raise ConfigError(
                        f"The requested job group {job_group} is not defined "
                        f"in the config files."
                    )

                # simply expand the groups to individual jobs
                self._jobs.update(self._config.job_groups[job_group])

        if "files" in self._args:
            # ensure that file list has unique elements
            self._args.files = set(self._args.files)
            # if not provided default it
            if not self._args.files:
                self._args.files = {"job-output.txt"}

    @property
    def jobs(self) -> Set[str]:
        return self._jobs

    @property
    def tenant(self) -> str:
        return self._args.tenant

    @property
    def project(self) -> Optional[str]:
        return self._args.project

    @property
    def pipeline(self) -> Optional[str]:
        return self._args.pipeline

    @property
    def branches(self) -> List[str]:
        return self._args.branches

    @property
    def result(self) -> Optional[str]:
        return self._args.result

    @property
    def voting(self) -> Optional[bool]:
        return self._args.voting

    @property
    def limit(self) -> int:
        return self._args.limit

    @property
    def regex(self) -> str:
        return self._args.regex

    @property
    def before_context(self) -> int:
        return self._args.before_context

    @property
    def after_context(self) -> int:
        return self._args.after_context

    @property
    def context(self) -> int:
        return self._args.context

    @property
    def log_store_dir(self) -> str:
        return self._args.log_store_dir

    @property
    def files(self) -> Set[str]:
        return self._args.files

    @property
    def uuid(self) -> str:
        return self._args.uuid
