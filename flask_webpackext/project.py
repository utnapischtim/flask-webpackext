# -*- coding: utf-8 -*-
#
# This file is part of Flask-WebpackExt
# Copyright (C) 2017, 2018 CERN.
# Copyright (C) 2024-2025 Graz University of Technology.
#
# Flask-WebpackExt is free software; you can redistribute it and/or modify
# it under the terms of the Revised BSD License; see LICENSE file for
# more details.

"""Webpack project utilities for Flask-WebpackExt."""

from os.path import join

from flask import current_app
from flask.helpers import get_root_path
from pynpm import NPMPackage
from pywebpack import WebpackBundleProject as PyWebpackBundleProject
from pywebpack import WebpackTemplateProject as PyWebpackTemplateProject
from pywebpack.helpers import cached
from werkzeug.utils import import_string


class PNPMPackage(NPMPackage):
    """Change to pnpm."""

    def __init__(self, filepath, npm_bin="pnpm", commands=None, shell=False):
        """Construct."""
        super().__init__(
            filepath=filepath, npm_bin=npm_bin, commands=commands, shell=shell
        )

    def _run_npm(self, command, *args, **kwargs):
        """Run an NPM command.

        By default the call is blocking until NPM is finished and output
        is directed to stdout. If ``wait=False`` is passed to the method,
        you get a handle to the process (return value of ``subprocess.Popen``).

        :param command: NPM command to run.
        :param args: List of arguments.
        :param wait: Wait for NPM command to finish. By defaul
        """
        if command == "install":
            args = ["--shamefully-hoist"]

        return super()._run_npm(command, *args, **kwargs)


class _PathStorageMixin:
    """Mixin class."""

    @property
    def path(self):
        """Get path to project."""
        try:
            return self.app.config["WEBPACKEXT_PROJECT_BUILDDIR"]
        except KeyError:
            return join(self.app.instance_path, "assets")

    @property
    def dist_dir(self):
        """Get dist dir."""
        try:
            return self.app.config["WEBPACKEXT_PROJECT_DISTDIR"]
        except KeyError:
            return join(self.app.static_folder, "dist")

    @property
    def project(self):
        project = self.app.config["WEBPACKEXT_PROJECT"]
        if isinstance(project, str):
            return import_string(project)
        return project

    @property
    @cached
    def npmpkg(self):
        """Get API to NPM package."""
        js_packages_manager = self.app.config.get("JAVASCRIPT_PACKAGES_MANAGER", "npm")
        if js_packages_manager == "pnpm":
            return PNPMPackage(self.path)

        return NPMPackage(self.path)

    def run(self, script_name, *args):
        """Override run."""
        assets_builder = self.app.config.get("ASSETS_BUILDER", "webpack")
        if assets_builder == "rspack":
            script_name += "-rspack"
        return super().run(script_name, *args)

    @property
    def storage_cls(self):
        """Get storage class."""
        cls_ = self.app.config["WEBPACKEXT_STORAGE_CLS"]
        if isinstance(cls_, str):
            return import_string(cls_)
        return cls_

    def flask_config(self):
        """Flask configuration injected in Webpack.

        :return: Dictionary which contains the information Flask-WebpackExt knows
        about a Webpack project and the absolute URLs for static files and
        assets. The dictionary consists of a key ``build`` with the following
        keys inside:

        * ``debug``: Boolean which represents if Flask debug is on.
        * ``context``: Absolute path to the generated assets directory.
        * ``assetsPath``: Absolute path to the generated static directory.
        * ``assetsURL``: URL to access the built files.
        * ``staticPath``: Absolute path to the generated static directory.
        * ``staticURL``: URL to access the static files..
        """
        assets_url = self.app.config["WEBPACKEXT_PROJECT_DISTURL"]
        if not assets_url.endswith("/"):
            assets_url += "/"
        static_url = self.app.static_url_path
        if not static_url.endswith("/"):
            static_url += "/"

        return {
            "build": {
                "debug": self.app.debug,
                "context": self.project.path,
                "assetsPath": self.app.config["WEBPACKEXT_PROJECT_DISTDIR"],
                "assetsURL": assets_url,
                "staticPath": self.app.static_folder,
                "staticURL": static_url,
            }
        }

    def flask_allowed_copy_paths(self):
        """Get the allowed copy paths from the Flask application."""
        return [
            self.app.instance_path,
            self.path,
            self.app.static_folder,
            self.dist_dir,
        ]


class WebpackTemplateProject(_PathStorageMixin, PyWebpackTemplateProject):
    """Flask webpack template project."""

    def __init__(
        self, import_name, project_folder=None, config=None, config_path=None, app=None
    ):
        """Initialize project.

        :param import_name: Name of the module where the
            WebpackTemplateProject class is instantiated. It is used to
            determine the absolute path to the ``project_folder``.
        :param project_folder: Relative path to the Webpack project.
        :param config: Dictionary which overrides the ``config.json`` file
            generated by Flask-WebpackExt. Use carefuly and only if you know
            what you are doing since ``config.json`` is the file that holds the
            key information to integrate Flask with Webpack.
        :param config_path: Path where Flask-WebpackExt is going to write the
            ``config.json``, this file is generated by
            :func:`flask_webpackext.project.flask_config`.
        """
        self.app = app or current_app
        project_template_dir = join(get_root_path(import_name), project_folder)

        super().__init__(
            None,
            project_template_dir=project_template_dir,
            config=config or self.flask_config,
            config_path=config_path,
        )


class WebpackBundleProject(_PathStorageMixin, PyWebpackBundleProject):
    """Flask webpack bundle project."""

    def __init__(
        self,
        import_name,
        project_folder=None,
        bundles=None,
        config=None,
        config_path=None,
        allowed_copy_paths=None,
        app=None,
    ):
        """Initialize templated folder.

        :param import_name: Name of the module where the WebpackBundleProject
            class is instantiated. It is used to determine the absolute path
            to the ``project_folder``.
        :param project_folder: Relative path to the Webpack project which is
            going to aggregate all the ``bundles``.
        :param bundles: List of
            :class:`flask_webpackext.bundle.WebpackBundle`. This list can be
            statically defined if the bundles are known before hand, or
            dinamically generated using
            :func:`pywebpack.helpers.bundles_from_entry_point` so the bundles
            are discovered from the defined Webpack entrypoints exposed by
            other modules.
        :param config: Dictionary which overrides the ``config.json`` file
            generated by Flask-WebpackExt. Use carefuly and only if you know
            what you are doing since ``config.json`` is the file that holds the
            key information to integrate Flask with Webpack.
        :param config_path: Path where Flask-WebpackExt is going to write the
            ``config.json``, this file is generated by
            :func:`flask_webpackext.project.flask_config`.
        :param allowed_copy_paths: List of paths (absolute, or relative to
            the `config_path`) that are allowed for bundle copy instructions.
        """
        self.app = app or current_app
        project_template_dir = join(get_root_path(import_name), project_folder)
        config = config or self.flask_config
        allowed_copy_paths = allowed_copy_paths or self.flask_allowed_copy_paths()
        super().__init__(
            None,
            project_template_dir=project_template_dir,
            bundles=bundles,
            config=config,
            config_path=config_path,
            allowed_copy_paths=allowed_copy_paths,
        )

    @property
    @cached
    def entry(self):
        """Get webpack entry points."""
        # this enables to use the bundle without the current_app context
        for bundle in self.bundles:
            bundle.app = self.app

        return super().entry
