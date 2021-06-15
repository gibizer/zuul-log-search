import argparse
import logging
import os
from typing import Dict, List, Set
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
        self._config = PersistentConfig(args.config_dir)
        self._jobs: set[str] = set()
        self._init_from_args(args)

    def _init_from_args(self, args: argparse.Namespace) -> None:
        # calculate jobs from command line and expand requested job groups
        if "jobs" in args:
            self._jobs = set(args.jobs)
            for job_group in args.job_groups:
                if job_group not in self._config.job_groups:
                    raise ConfigError(
                        f"The requested job group {job_group} is not defined "
                        f"in the config files."
                    )

                # simply expand the groups to individual jobs
                self._jobs.update(self._config.job_groups[job_group])

    @property
    def jobs(self) -> Set[str]:
        return self._jobs
