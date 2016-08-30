# -*- coding: utf-8 -*-
#                     The LLVM Compiler Infrastructure
#
# This file is distributed under the University of Illinois Open Source
# License. See LICENSE.TXT for details.

import os
import sys
#import datetime
import socket

from thrift.transport import THttpClient
from thrift.protocol import TJSONProtocol

from codeCheckerDBAccess import codeCheckerDBAccess
import shared


class ThriftClientHelper():

    def __init__(self, host, port, uri):
        self.transport = THttpClient.THttpClient(host, port, uri)
        self.protocol = TJSONProtocol.TJSONProtocol(self.transport)
        self.client = codeCheckerDBAccess.Client(self.protocol)

# ------------------------------------------------------------
    def ThriftClientCall(function):
        #print type(function)
        funcName = function.__name__
        def wrapper(self, *args, **kwargs):
            #print('['+host+':'+str(port)+'] >>>>> ['+funcName+']')
            #before = datetime.datetime.now()
            self.transport.open()
            func = getattr(self.client,funcName)
            try:
                res = func(*args, **kwargs)

            except shared.ttypes.RequestFailed as reqfailure:
                if reqfailure.error_code == shared.ttypes.ErrorCode.DATABASE:

                    print(str(reqfailure.message))
                else:
                    print('Other error')
                    print(str(reqfailure))

                sys.exit(1)

            except socket.error as serr:
                errCause = os.strerror(serr.errno)
                print(errCause)
                print(str(serr))
                sys.exit(1)


            #after = datetime.datetime.now()
            #timediff = after - before
            #diff = timediff.microseconds/1000
            #print('['+str(diff)+'ms] <<<<< ['+host+':'+str(port)+']')
            #print res
            self.transport.close()
            return res

        return wrapper

    # ------------------------------------------------------------
    @ThriftClientCall
    def getRunData():
        pass

    # ------------------------------------------------------------
    @ThriftClientCall
    def getRunResults(self, runId, resultBegin, resultEnd, sortType, reportFilters):
        pass

    # ------------------------------------------------------------
    @ThriftClientCall
    def getRunResultCount(self, runId, reportFilters):
        pass

    #-----------------------------------------------------------------------
    @ThriftClientCall
    def getRunResultTypes(self, runId, reportFilters):
        pass

    #-----------------------------------------------------------------------
    @ThriftClientCall
    def getAPIVersion(self):
        pass

    #-----------------------------------------------------------------------
    @ThriftClientCall
    def removeRunResults(self, run_ids):
        pass

    #-----------------------------------------------------------------------
    @ThriftClientCall
    def getNewResults(self, base_run_id, new_run_id, limit, offset, sortType, reportFilters):
        pass

    #-----------------------------------------------------------------------
    @ThriftClientCall
    def getUnresolvedResults(self, base_run_id, new_run_id, limit, offset, sortType, reportFilters):
        pass

    #-----------------------------------------------------------------------
    @ThriftClientCall
    def getResolvedResults(self, base_run_id, new_run_id, limit, offset, sortType, reportFilters):
        pass
