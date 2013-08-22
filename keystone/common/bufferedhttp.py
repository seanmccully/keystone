# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright (c) 2010-2012 OpenStack, LLC.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Monkey Patch httplib.HTTPResponse to buffer reads of headers. This can improve
performance when making large numbers of small HTTP requests.  This module
also provides helper functions to make HTTP connections using
BufferedHTTPResponse.

.. warning::

    If you use this, be sure that the libraries you are using do not access
    the socket directly (xmlrpclib, I'm looking at you :/), and instead
    make all calls through httplib.
"""

import time
import urllib

from eventlet.green import httplib

from keystone.common import logging


LOG = logging.getLogger(__name__)


class BufferedHTTPResponse(httplib.HTTPResponse):
    """HTTPResponse class that buffers reading of headers."""

    def __init__(self, sock, debuglevel=0, strict=0,
                 method=None):          # pragma: no cover
        self.sock = sock
        self.fp = sock.makefile('rb')
        self.debuglevel = debuglevel
        self.strict = strict
        self._method = method

        self.msg = None

        # from the Status-Line of the response
        self.version = httplib._UNKNOWN  # HTTP-Version
        self.status = httplib._UNKNOWN  # Status-Code
        self.reason = httplib._UNKNOWN  # Reason-Phrase

        self.chunked = httplib._UNKNOWN  # is "chunked" being used?
        self.chunk_left = httplib._UNKNOWN  # bytes left to read in chunk
        self.length = httplib._UNKNOWN  # number of bytes left in response
        self.will_close = httplib._UNKNOWN  # conn will close at end of resp

    def expect_response(self):
        self.fp = self.sock.makefile('rb', 0)
        version, status, reason = self._read_status()
        if status != httplib.CONTINUE:
            self._read_status = lambda: (version, status, reason)
            self.begin()
        else:
            self.status = status
            self.reason = reason.strip()
            self.version = 11
            self.msg = httplib.HTTPMessage(self.fp, 0)
            self.msg.fp = None


class BufferedHTTPConnection(httplib.HTTPConnection):
    """HTTPConnection class that uses BufferedHTTPResponse."""
    response_class = BufferedHTTPResponse

    def connect(self):
        self._connected_time = time.time()
        return httplib.HTTPConnection.connect(self)

    def putrequest(self, method, url, skip_host=0, skip_accept_encoding=0):
        self._method = method
        self._path = url
        return httplib.HTTPConnection.putrequest(self, method, url, skip_host,
                                                 skip_accept_encoding)

    def getexpect(self):
        response = BufferedHTTPResponse(self.sock, strict=self.strict,
                                        method=self._method)
        response.expect_response()
        return response

    def getresponse(self):
        response = httplib.HTTPConnection.getresponse(self)
        LOG.debug(_('HTTP PERF: %(time).5f seconds to %(method)s '
                  '%(host)s:%(port)s %(path)s)'),
                  {'time': time.time() - self._connected_time,
                   'method': self._method,
                   'host': self.host,
                   'port': self.port,
                   'path': self._path})
        return response


def http_connect(ipaddr, port, device, partition, method, path,
                 headers=None, query_string=None, ssl=False, key_file=None,
                 cert_file=None):
    """Helper function to create an HTTPConnection object.

    If ssl is set True, HTTPSConnection will be used. However, if ssl=False,
    BufferedHTTPConnection will be used, which is buffered for backend Swift
    services.

    :param ipaddr: IPv4 address to connect to
    :param port: port to connect to
    :param device: device of the node to query
    :param partition: partition on the device
    :param method: HTTP method to request ('GET', 'PUT', 'POST', etc.)
    :param path: request path
    :param headers: dictionary of headers
    :param query_string: request query string
    :param ssl: set True if SSL should be used (default: False)
    :param key_file Private key file (not needed if cert_file has private key)
    :param cert_file Certificate file (Keystore)
    :returns: HTTPConnection object

    """
    path = urllib.quote('/' + device + '/' + str(partition) + path)
    return http_connect_raw(ipaddr, port, device, partition, method, path,
                            headers, query_string, ssl, key_file, cert_file)


def http_connect_raw(ipaddr, port, method, path, headers=None,
                     query_string=None, ssl=False, key_file=None,
                     cert_file=None):
    """Helper function to create an HTTPConnection object.

    If ssl is set True, HTTPSConnection will be used. However, if ssl=False,
    BufferedHTTPConnection will be used, which is buffered for backend Swift
    services.

    :param ipaddr: IPv4 address to connect to
    :param port: port to connect to
    :param method: HTTP method to request ('GET', 'PUT', 'POST', etc.)
    :param path: request path
    :param headers: dictionary of headers
    :param query_string: request query string
    :param ssl: set True if SSL should be used (default: False)
    :param key_file Private key file (not needed if cert_file has private key)
    :param cert_file Certificate file (Keystore)
    :returns: HTTPConnection object

    """
    if ssl:
        conn = httplib.HTTPSConnection(
            '%s:%s' % (ipaddr, port), key_file=key_file, cert_file=cert_file)
    else:
        conn = BufferedHTTPConnection('%s:%s' % (ipaddr, port))
    if query_string:
        path += '?' + query_string
    conn.path = path
    conn.putrequest(method, path)
    if headers:
        for header, value in headers.iteritems():
            conn.putheader(header, value)
    conn.endheaders()
    return conn
