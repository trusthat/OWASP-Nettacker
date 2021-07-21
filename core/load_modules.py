#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import lib
import inspect
from glob import glob
from core.alert import messages
from core.alert import info
from core.alert import warn
from core._die import __die_failure
from core.compatible import version
from core.compatible import is_windows
from core.compatible import logo
from core.config import _core_config
from core.config_builder import _core_default_config
from core.config_builder import _builder

import yaml
import numpy
import json
import sys
from core.utility import expand_module_steps
from core import module_protocols
from io import StringIO


class module:
    def __init__(self):
        self.module_path = None
        self.module_content = None
        self.module_inputs = {}
        self.libraries = dir(module_protocols)

    def load(self):
        self.module_content = yaml.load(
            StringIO(
                open(self.module_path, 'r').read().format(
                    **self.module_inputs
                )
            ),
            Loader=yaml.FullLoader
        )

    def generate_loops(self):
        self.module_content['payloads'] = expand_module_steps(self.module_content['payloads'])

    def start(self):
        for payload in self.module_content['payloads']:
            if payload['library'] not in self.libraries:
                print('library [{library}] is not support!'.format(library=payload['library']))
                return None
            protocol = getattr(
                __import__(
                    'lib.module_protocols.{library}'.format(library=payload['library']),
                    fromlist=['engine']
                ),
                'engine'
            )
            for step in payload['steps']:
                for sub_step in step:
                    # must be multi thread here!
                    protocol.run(sub_step, payload)


def load_all_graphs():
    """
    load all available graphs

    Returns:
        an array of graph names
    """
    graph_names = []
    for _lib in glob(os.path.dirname(inspect.getfile(lib)) + '/graph/*/engine.py'):
        if os.path.dirname(_lib).rsplit('\\' if is_windows() else '/')[
            -2] == "graph" and _lib + '_graph' not in graph_names:
            _lib = _lib.rsplit('\\' if is_windows() else '/')[-2]
            graph_names.append(_lib + '_graph')
    return graph_names


def load_all_modules():
    """
    load all available modules

    Returns:
        an array of all module names
    """
    # Search for Modules
    module_names = []
    for _lib in glob(os.path.dirname(inspect.getfile(lib)) + '/*/*/engine.py'):
        libname = _lib.rsplit('\\' if is_windows() else '/')[-2]
        category = _lib.rsplit('\\' if is_windows() else '/')[-3]
        if (category != 'graph' and
                libname + '_' + category not in module_names):
            module_names.append(libname + '_' + category)
    module_names.append('all')
    return module_names


def load_all_method_args(language, API=False):
    """
    load all ARGS method for each module

    Args:
        language: language
        API: API Flag (default False)

    Returns:
        all ARGS method in JSON
    """
    module_names = []
    modules_args = {}
    # get module names
    for _lib in glob(os.path.dirname(inspect.getfile(lib)) + '/*/*/engine.py'):
        _lib = _lib.replace('/', '.').replace('\\', '.')
        if '.lib.brute.' in _lib or \
                '.lib.scan.' in _lib or '.lib.vuln.' in _lib:
            _lib = 'lib.' + _lib.rsplit('.lib.')[-1].rsplit('.py')[0]
            if _lib not in module_names:
                module_names.append(_lib)
    # get args
    res = ""
    for imodule in module_names:
        _ERROR = False
        try:
            extra_requirements_dict = getattr(__import__(
                imodule,
                fromlist=['extra_requirements_dict']),
                'extra_requirements_dict')
        except:
            warn(messages(language, "module_args_error").format(imodule))
            _ERROR = True
        if not _ERROR:
            imodule_args = extra_requirements_dict()
            modules_args[imodule] = []
            for imodule_arg in imodule_args:
                if API:
                    res += imodule_arg + "=" + \
                           ",".join(map(str, imodule_args[imodule_arg])) + "\n"
                modules_args[imodule].append(imodule_arg)
    if API:
        return res
    for imodule in modules_args:
        info(imodule.rsplit('.')[2] + '_' + imodule.rsplit('.')[1] + ' --> '
             + ", ".join(modules_args[imodule]))
    return module_names


def __check_external_modules():
    """
    check external libraries if they are installed

    Returns:
        True if success otherwise None
    """
    # check python version
    if version() == 2:
        logo()
        __die_failure(messages("en", "python_version_error"))

    external_modules = ["argparse", "netaddr", "requests",
                        "paramiko", "texttable", "socks",
                        "win_inet_pton",
                        "flask", "sqlalchemy"]
    for module in external_modules:
        try:
            __import__(module)
        except:
            __die_failure("pip3 install -r requirements.txt ---> " +
                          module + " not installed!")

    default_config = _builder(_core_config(), _core_default_config())

    if not os.path.exists(default_config["home_path"]):
        try:
            os.mkdir(default_config["home_path"])
            os.mkdir(default_config["tmp_path"])
            os.mkdir(default_config["results_path"])
        except:
            __die_failure("cannot access the directory {0}".format(
                default_config["home_path"]))
    if not os.path.exists(default_config["tmp_path"]):
        try:
            os.mkdir(default_config["tmp_path"])
        except:
            __die_failure("cannot access the directory {0}".format(
                default_config["results_path"]))
    if not os.path.exists(default_config["results_path"]):
        try:
            os.mkdir(default_config["results_path"])
        except:
            __die_failure("cannot access the directory {0}".format(
                default_config["results_path"]))
    if default_config["database_type"] == "sqlite":
        try:
            if os.path.isfile(
                    default_config[
                        "home_path"] + "/" + default_config["database_name"]):
                pass
            else:
                from database.sqlite_create import sqlite_create_tables
                sqlite_create_tables()
        except:
            __die_failure("cannot access the directory {0}".format(
                default_config["home_path"]))
    elif default_config["database_type"] == "mysql":
        try:
            from database.mysql_create import (
                mysql_create_tables,
                mysql_create_database)
            mysql_create_database()
            mysql_create_tables()
        except:
            __die_failure(messages("en", "database_connection_failed"))
    elif default_config["database_type"] == "postgres":
        try:
            from database.postgres_create import postgres_create_database
            postgres_create_database()
        except Exception as e:
            __die_failure(messages("en", "database_connection_failed"))
    else:
        __die_failure(messages("en", "invalid_database"))
    return True


def load_file_path():
    """
    load home path

    Returns:
        value of home path
    """
    return _builder(_core_config(), _core_default_config())["home_path"]
