import os
import unittest
from unittest import mock

from logsearch import main


class TestArgs(unittest.TestCase):
    def _parse(self, argv):
        handler = main.ArgHandler(
            build_handler=None,
            build_show_handler=None,
            logsearch_handler=None,
            stored_search_handler=None,
            match_handler=None,
            cache_show_handler=None,
            cache_purge_handler=None,
        )
        return handler._parse_args(argv)

    def test_config_dir_provided(self):
        argv = ["--config-dir", "foo/bar"]
        with mock.patch("os.path.exists", return_value=False):
            args = self._parse(argv)

        self.assertEqual("foo/bar", args.config_dir)

    def test_config_dir_provided_so_pwd_ignored(self):
        argv = ["--config-dir", "foo/bar"]
        with mock.patch("os.path.exists", return_value=True):
            args = self._parse(argv)

        self.assertEqual("foo/bar", args.config_dir)

    def test_config_dir_provided_so_xdg_ignored(self):
        argv = ["--config-dir", "foo/bar"]
        with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": "baz/boo"}):
            args = self._parse(argv)

        self.assertEqual("foo/bar", args.config_dir)

    def test_config_dir_defaulted_pwd_exists(self):
        with mock.patch("os.path.exists", return_value=True):
            args = self._parse([])

        self.assertEqual(".logsearch.conf.d/", args.config_dir)

    def test_config_dir_defaulted_pwd_not_exists(self):
        with (
            mock.patch("os.path.exists", return_value=False),
            mock.patch.dict(os.environ, {"HOME": "/home/user123"}),
        ):
            args = self._parse([])

        self.assertEqual("/home/user123/.config/logsearch", args.config_dir)

    def test_config_dir_defaulted_via_xdg_config_home(self):
        with (
            mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": "foo/bar"}),
            mock.patch("os.path.exists", return_value=False),
        ):
            args = self._parse([])

        self.assertEqual("foo/bar/logsearch", args.config_dir)
