# -*- coding: utf-8 -*-
#                     The LLVM Compiler Infrastructure
#
# This file is distributed under the University of Illinois Open Source
# License. See LICENSE.TXT for details.
'''
'''

import os
import sys
import signal
import multiprocessing
import ntpath
import traceback
import shutil
from collections import defaultdict

from libcodechecker import logger
from libcodechecker import analyzer_env

from libcodechecker.analyzers import analyzer_types

LOG = logger.get_new_logger('ANALISYS MANAGER')


def worker_result_handler(results):
    """
    print the analisys summary
    """

    successful_analysis = defaultdict(int)
    failed_analisys = defaultdict(int)
    skipped_num = 0

    for res, skipped, analyzer_type in results:
        if skipped:
            skipped_num += 1
        else:
            if res == 0:
                successful_analysis[analyzer_type] += 1
            else:
                failed_analisys[analyzer_type] += 1

    LOG.info("----==== Summary ====----")
    LOG.info('Total compilation commands: ' + str(len(results)))
    if successful_analysis:
        LOG.info('Successfully analyzed')
        for analyzer_type, res in successful_analysis.iteritems():
            LOG.info('  ' + analyzer_type + ': ' + str(res))

    if failed_analisys:
        LOG.info("Failed to analyze")
        for analyzer_type, res in failed_analisys.iteritems():
            LOG.info('  ' + analyzer_type + ': ' + str(res))

    if skipped_num:
        LOG.info('Skipped compilation commands: ' + str(skipped_num))
    LOG.info("----=================----")

def check(check_data):
    """
    Invoke clang with an action which called by processes.
    Different analyzer object belongs to for each build action

    skiplist handler is None if no skip file was configured
    """
    args, action, context, analyzer_config_map, skp_handler, \
        report_output_dir, use_db = check_data

    skipped = False
    try:
        # if one analysis fails the check fails
        return_codes = 0
        skipped = False
        for source in action.sources:

            # if there is no skiplist handler there was no skip list file
            # in the command line
            # cpp file skipping is handled here
            _, source_file_name = ntpath.split(source)

            if skp_handler and skp_handler.should_skip(source):
                LOG.debug_analyzer(source_file_name + ' is skipped')
                skipped = True
                continue

            # construct analyzer env
            analyzer_environment = analyzer_env.get_check_env(context.path_env_extra,
                                                      context.ld_lib_path_extra)
            run_id = context.run_id

            rh = analyzer_types.construct_result_handler(args,
                                                         action,
                                                         run_id,
                                                         report_output_dir,
                                                         context.severity_map,
                                                         skp_handler,
                                                         use_db)

            #LOG.info('Analysing ' + source_file_name)

            # create a source analyzer
            source_analyzer = analyzer_types.construct_analyzer(action,
                                                                analyzer_config_map)

            # source is the currently analyzed source file
            # there can be more in one buildaction
            source_analyzer.source_file = source

            # fills up the result handler with the analyzer information
            source_analyzer.analyze(rh, analyzer_environment)

            if rh.analyzer_returncode == 0:
                # analysis was successful
                # processing results
                if rh.analyzer_stdout != '':
                    LOG.debug_analyzer('\n' + rh.analyzer_stdout)
                if rh.analyzer_stderr != '':
                    LOG.debug_analyzer('\n' + rh.analyzer_stderr)
                rh.postprocess_result()
                rh.handle_results()
            else:
                # analisys failed
                LOG.error('Analyzing ' + source_file_name + ' failed.')
                if rh.analyzer_stdout != '':
                    LOG.error(rh.analyzer_stdout)
                if rh.analyzer_stderr != '':
                    LOG.error(rh.analyzer_stderr)
                return_codes = rh.analyzer_returncode

            if not args.keep_tmp:
                rh.clean_results()

        return (return_codes, skipped, action.analyzer_type)

    except Exception as e:
        LOG.debug_analyzer(str(e))
        traceback.print_exc(file=sys.stdout)
        return (1, skipped, action.analyzer_type)

def start_workers(args, actions, context, analyzer_config_map, skp_handler):
    """
    start the workers in the process pool
    for every buildaction there is worker which makes the analysis
    """

    # Handle SIGINT to stop this script running
    def signal_handler(*arg, **kwarg):
        try:
            pool.terminate()
        finally:
            sys.exit(1)

    signal.signal(signal.SIGINT, signal_handler)

    # create report output dir this will be used by the result handlers for each
    # analyzer to store analyzer results or temporary files
    # each analyzer instance does its own cleanup
    report_output = os.path.join(context.codechecker_workspace,
                                 args.name + '_reports')

    if not os.path.exists(report_output):
        os.mkdir(report_output)

    # Start checking parallel
    pool = multiprocessing.Pool(args.jobs)
    # pool.map(check, actions, 1)

    try:
        # Workaround, equialent of map
        # The main script does not get signal
        # while map or map_async function is running
        # It is a python bug, this does not happen if a timeout is specified;
        # then receive the interrupt immediately

        analyzed_actions = [(args,
                             build_action,
                             context,
                             analyzer_config_map,
                             skp_handler,
                             report_output,
                             True ) for build_action in actions]

        pool.map_async(check,
                       analyzed_actions,
                       1,
                       callback=worker_result_handler).get(float('inf'))

        pool.close()
    except Exception:
        pool.terminate()
        raise
    finally:
        pool.join()
        if not args.keep_tmp:
            LOG.debug('Removing temporary directory: ' + report_output)
            shutil.rmtree(report_output)
