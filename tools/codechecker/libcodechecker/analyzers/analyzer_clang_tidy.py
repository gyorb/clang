# -*- coding: utf-8 -*-
#                     The LLVM Compiler Infrastructure
#
# This file is distributed under the University of Illinois Open Source
# License. See LICENSE.TXT for details.

'''
'''

import re
import subprocess
import shlex

from libcodechecker import logger

from libcodechecker.analyzers import analyzer_base

LOG = logger.get_new_logger('CLANG TIDY')


class ClangTidy(analyzer_base.SourceAnalyzer):
    """
    constructs the clang tidy analyzer commands
    """

    def __parse_checkers(self, tidy_output):
        """
        parse clang tidy checkers list
        skip clang static analyzer checkers
        store them to checkers
        """
        for line in tidy_output.splitlines():
            line = line.strip()
            if re.match(r'^Enabled checks:', line) or line == '':
                continue
            elif line.startswith('clang-analyzer-'):
                continue
            else:
                match = re.match(r'^\S+$', line)
                if match:
                    self.checkers.append((match.group(0), ''))

    def get_analyzer_checkers(self, config_handler, env):
        """
        return the list of the supported checkers
        """
        if not self.checkers:
            analyzer_binary = config_handler.analyzer_binary

            command = [analyzer_binary]
            command.append("-list-checks")
            command.append("-checks='*'")
            command.append("-")
            command.append("--")

            try:
                command = shlex.split(' '.join(command))
                result = subprocess.check_output(command,
                                                 env=env)
            except subprocess.CalledProcessError as cperr:
                LOG.error(cperr)
                return {}

            self.__parse_checkers(result)

        return self.checkers

    def construct_analyzer_cmd(self, res_handler):
        """
        """
        try:
            config = self.config_handler

            analyzer_bin = config.analyzer_binary

            analyzer_cmd = []
            analyzer_cmd.append(analyzer_bin)

            # disable all checkers by default
            checkers_cmdline = '-*'

            # config handler stores which checkers are enabled or disabled
            for checker_name, value in config.checks().iteritems():
                enabled, _ = value
                if enabled:
                    checkers_cmdline += ',' + checker_name
                else:
                    checkers_cmdline += ',-' + checker_name

            analyzer_cmd.append("-checks='" + checkers_cmdline.lstrip(',') + "'")

            LOG.debug(config.analyzer_extra_arguments)
            analyzer_cmd.append(config.analyzer_extra_arguments)

            analyzer_cmd.append(self.source_file)

            analyzer_cmd.append("--")

            extra_arguments_before = []
            if len(config.compiler_resource_dirs) > 0:
                for inc_dir in config.compiler_resource_dirs:
                    extra_arguments_before.append('-resource-dir')
                    extra_arguments_before.append(inc_dir)
                    extra_arguments_before.append('-isystem')
                    extra_arguments_before.append(inc_dir)

            if config.compiler_sysroot:
                extra_arguments_before.append('--sysroot')
                extra_arguments_before.append(config.compiler_sysroot)

            for path in config.system_includes:
                extra_arguments_before.append('-isystem')
                extra_arguments_before.append(path)

            for path in config.includes:
                extra_arguments_before.append('-I')
                extra_arguments_before.append(path)

            # Set lang
            extra_arguments_before.append('-x')
            extra_arguments_before.append(self.buildaction.lang)

            analyzer_cmd.append(' '.join(extra_arguments_before))

            analyzer_cmd.extend(self.buildaction.analyzer_options)

            return analyzer_cmd

        except Exception as ex:
            LOG.error(ex)
            return []
