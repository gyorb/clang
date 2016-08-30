# -*- coding: utf-8 -*-
#                     The LLVM Compiler Infrastructure
#
# This file is distributed under the University of Illinois Open Source
# License. See LICENSE.TXT for details.

import os
import collections

from abc import ABCMeta, abstractmethod

from libcodechecker import logger

LOG = logger.get_new_logger('CONFIG HANDLER')

class AnalyzerConfigHandler(object):
    """
    handle the checker configurations
    and enabled disabled checkers lists
    """
    __metaclass__ = ABCMeta

    def __init__(self):

        self.__analyzer_binary = None
        self.__analyzer_plugins_dir = None
        self.__compiler_sysroot = None
        self.__compiler_resource_dirs = []
        self.__sys_inc = []
        self.__includes = []
        self.__analyzer_extra_arguments = ''

        # the key is the checker name, the value is a tuple
        # False if disabled (should be by default)
        # True if checker is enabled
        # (False/True, 'checker_description')
        self.__available_checkers = collections.OrderedDict()

    @property
    def analyzer_plugins_dir(self):
        """
        get directory from where shared objects with checkers should be loaded
        """
        return self.__analyzer_plugins_dir

    @analyzer_plugins_dir.setter
    def analyzer_plugins_dir(self, value):
        """
        set the directory where shared objects with checkers can be found
        """
        self.__analyzer_plugins_dir = value

    @property
    def analyzer_plugins(self):
        """
        full path of the analyzer plugins
        """
        plugin_dir = self.__analyzer_plugins_dir
        analyzer_plugins = [os.path.join(plugin_dir, f)
                            for f in os.listdir(plugin_dir)
                            if os.path.isfile(os.path.join(plugin_dir, f))]
        return analyzer_plugins

    @property
    def analyzer_binary(self):
        return self.__analyzer_binary

    @analyzer_binary.setter
    def analyzer_binary(self, value):
        self.__analyzer_binary = value

    @abstractmethod
    def get_checker_configs(self):
        """
        return a lis of (checker_name, key, key_valye) tuples
        """
        pass

    def add_checker(self, checker_name, enabled, description):
        """
        add additional checker
        tuple of (checker_name, True\False)
        """
        self.__available_checkers[checker_name] = (enabled, description)

    def enable_checker(self, checker_name, description=None):
        """
        enable checker, keep description if already set
        """
        for ch_name, values in self.__available_checkers.iteritems():
            if ch_name.startswith(checker_name):
                _, description = values
                self.__available_checkers[ch_name] = (True, description)

    def disable_checker(self, checker_name, description=None):
        """
        disable checker, keep description if already set
        """
        for ch_name, values in self.__available_checkers.iteritems():
            if ch_name.startswith(checker_name):
                _, description = values
                self.__available_checkers[ch_name] = (False, description)

    def checks(self):
        """
        return the checkers
        """
        return self.__available_checkers

    @property
    def compiler_sysroot(self):
        """
        get compiler sysroot
        """
        return self.__compiler_sysroot

    @compiler_sysroot.setter
    def compiler_sysroot(self, compiler_sysroot):
        """
        set compiler sysroot
        """
        self.__compiler_sysroot = compiler_sysroot

    @property
    def compiler_resource_dirs(self):
        """
        set compiler resource directories
        """
        return self.__compiler_resource_dirs

    @compiler_resource_dirs.setter
    def compiler_resource_dirs(self, resource_dirs):
        """
        set compiler resource directories
        """
        self.__compiler_resource_dirs = resource_dirs

    @property
    def system_includes(self):
        """
        """
        return self.__sys_inc

    @system_includes.setter
    def system_includes(self, includes):
        """
        """
        self.__sys_inc = includes

    def add_system_includes(self, sys_inc):
        """
        add additional system includes if needed
        """
        self.__sys_inc.append(sys_inc)

    @property
    def includes(self):
        """
        add additional includes if needed
        """
        return self.__includes

    @includes.setter
    def includes(self, includes):
        """
        add additional includes if needed
        """
        self.__includes = includes

    def add_includes(self, inc):
        """
        add additional include paths
        """
        self.__includes.append(inc)

    @property
    def analyzer_extra_arguments(self):
        """
        extra arguments fowarded to the analyzer without modification
        """
        return self.__analyzer_extra_arguments

    @analyzer_extra_arguments.setter
    def analyzer_extra_arguments(self, value):
        """
        extra arguments fowarded to the analyzer without modification
        """
        self.__analyzer_extra_arguments = value
