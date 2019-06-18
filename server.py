#!/usr/bin/env python

import os
from http.server import *
from http.client import *
import ssl
from socketserver import ThreadingMixIn
import threading
import time
import re
import urllib
import json
import gzip
import datetime
import fakeapi
import sys
import getopt

SERVER_HOST="localhost"
CHANNEL_ID="12345678"
urlpatterns = []

class UrlError(Exception):
    pass

# shitty django urlpatterns
# Uh, kind of convoluted
def call_method(instance, request, name, kwargs):
    method = getattr(instance.__class__, name)
    if not method:
        raise KeyError(f"No such method: {name}")
    return method(instance, request, **kwargs)

def url(r, name, default={}):
    regex = re.compile(r, flags=re.IGNORECASE)
    def call_api(request, instance, uri, qs):
        m = regex.search(uri)
        if not m:
            return (False, None,)
        qs.update(default)
        qs.update(m.groupdict())
        print ("Matched url pattern:",name)
        return (True, call_method(instance, request, name, qs),)
    return call_api

def createUrlPatterns():
    global urlpatterns
    urlpatterns = [
        url(r'^/users/self/channels.json', 'do_users_channels', default={'host': SERVER_HOST, "channelid": CHANNEL_ID}),
        url(r'^/channel/(?P<channelid>.*)', 'do_channel'),
    ]

def range_tuple_normalize(range_tup):
    """Normalize a (first_byte,last_byte) range tuple.
    Return a tuple whose first element is guaranteed to be an int
    and whose second element will be '' (meaning: the last byte) or
    an int. Finally, return None if the normalized tuple == (0,'')
    as that is equivelant to retrieving the entire file.
    """
    if range_tup is None: return None
    # handle first byte
    fb = range_tup[0]
    if fb in (None,''): fb = 0
    else: fb = int(fb)
    # handle last byte
    try: lb = range_tup[1]
    except IndexError: lb = ''
    else:
        if lb is None: lb = ''
        elif lb != '': lb = int(lb)
    # check if range is over the entire file
    if (fb,lb) == (0,''): return None
    # check that the range is valid
    if lb != '' and lb < fb: raise RangeError('Invalid byte range: %s-%s' % (fb,lb))
    return (fb,lb)

_rangere = None
def range_header_to_tuple(range_header):
    """Get a (firstbyte,lastbyte) tuple from a Range header value.
    
    Range headers have the form "bytes=<firstbyte>-<lastbyte>". This
    function pulls the firstbyte and lastbyte values and returns
    a (firstbyte,lastbyte) tuple. If lastbyte is not specified in
    the header value, it is returned as an empty string in the
    tuple.
    
    Return None if range_header is None
    Return () if range_header does not conform to the range spec 
    pattern.
    
    """
    global _rangere
    if range_header is None: return None
    if _rangere is None:
        import re
        _rangere = re.compile(r'^bytes=(\d{1,})-(\d*)')
    match = _rangere.match(range_header)
    if match: 
        tup = range_tuple_normalize(match.group(1,2))
        if tup and tup[1]: 
            tup = (tup[0],tup[1]+1)
        return tup
    return ()

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in a separate thread."""
    pass

class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    fakeapi = fakeapi.API()

    def do_GET(self):
        """Serve a GET request."""
        qs = {}
        path = self.path
        parsed = urllib.parse.urlparse(path)
        qs = urllib.parse.parse_qs(parsed.query)
        #print (path, parsed, qs)
        #print (self.headers)
        host = self.headers.get('Host')
        host_path = host if host and host != 'localhost' else "."
        
        try:
            self.service_api_GET(parsed, qs)
            return
        except UrlError as e:
            print (e)

        self.send_response(404)
        self.end_headers()

    def do_HEAD(self):
        """Serve a HEAD request."""
        qs = {}
        path = self.path
        parsed = urllib.parse.urlparse(path)
        qs = urllib.parse.parse_qs(parsed.query)
        print (path, parsed, qs)
        print (self.headers)
        host = self.headers.get('Host')
        host_path = host if host and host != 'localhost' else "."
        
        file_path = f"./files/{host_path}/{path}"
        if os.path.exists(file_path):
            file_size = os.stat(file_path).st_size
            content_size = file_size
            byte_range = self.headers.get('Range')
            brange_tuple = None
            
            try:
                if byte_range:
                    brange_tuple = range_header_to_tuple(byte_range)
                    print ("brange_tuple", brange_tuple)
            except RangeError:
                pass # TODO Apache2 seems to just upload whole file
            
            if brange_tuple:
                if brange_tuple[1] != '':
                    content_size = brange_tuple[1] - brange_tuple[0]
                else:
                    content_size = file_size - brange_tuple[0]
            
            if content_size > file_size:
                content_size = file_size
                brange_tuple = None
            
            ctype = "application/octet-stream"
            
            if file_path[-5:] == ".html":
                ctype = "text/html"
            elif file_path[-3:] == ".js":
                ctype = "text/javascript"
            elif file_path[-4:] == ".css":
                ctype = "text/css"
            elif file_path[-4:] == ".mp3":
                ctype = "audio/mpeg"
            elif file_path[-4:] == ".aac":
                ctype = "audio/aac"
            elif file_path[-5:] == ".m3u8":
                #ctype = "vnd.apple.mpegURL"
                #ctype = "audio/x-mpegurl"
                ctype = "application/vnd.apple.mpegurl"
            elif file_path[-3:] == ".ts":
                ctype = "video/mp2t"
            
            self.send_response(200 if not brange_tuple else 206)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header("Content-Type", ctype)
            if brange_tuple:
                self.send_header("Accept-Ranges", 'bytes')
                self.send_header("Content-Range", 'bytes {}-{}/{}'.format(*brange_tuple, file_size))
            self.send_header("Content-Length", str(content_size))
            self.end_headers()
        else:
            self.send_response(405)
            self.end_headers()

    def do_POST(self):
        """Serve a POST request."""
        print ("SimpleHTTP POST, by: ", self.client_address, 'host:', self.headers.get('Host'), self.path)
        #qs = {}
        parsed = urllib.parse.urlparse(self.path)
        #qs = urllib.parse.parse_qs(parsed.query)
        print (self.headers)
        host = self.headers.get('Host')
        

    # shitty django urlpatterns
    def service_api_GET(self, path, qs):
        f = None
        ret = False
        
        for k,v in qs.items():
            print("qs:", k, v)
            # XXX Converting multiple params into one
            # you might actually want all of it if passing an array with GET
            if isinstance(v, list): v = v[0]
            qs[k] = v
        
        for x in urlpatterns:
            ret, f = x(self, self.fakeapi, path.path, qs)
            if ret: break
        
        if not ret:
            raise UrlError("Could not match an url pattern")

    def send_json(self, f, headers={}):
        length = f.tell()
        f.seek(0)
        self.send_response(200)
        for k,v in headers.items():
            self.send_header(k, v)
        self.send_header("Content-Type", "application/json; charset=UTF-8")
        self.send_header("Content-Length", str(length))
        self.end_headers()
        v = f.getvalue()
        #print (len(v), v)
        self.wfile.write(v)

    def send_html(self, f, headers={}):
        length = f.tell()
        f.seek(0)
        self.send_response(200)
        for k,v in headers.items():
            self.send_header(k, v)
        
        self.send_header("Content-Type", "text/html; charset=UTF-8")
        self.send_header("Content-Length", str(length))
        self.end_headers()
        self.wfile.write(f.getvalue())

def run(server_class=ThreadedHTTPServer, handler_class=SimpleHTTPRequestHandler):
    server_address = ('', 80)
    httpd = server_class(server_address, handler_class)
    httpd.serve_forever()


def usage():
    print ("""
    Usage:
    -s, --server\t Specify streaming server host address
    -i, --channelid\t Specify channel id the device was registered with
    """)

if __name__ == '__main__':
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hs:i:", ["help", "server=", "channelid="])
        for o, a in opts:
            if o == "-v":
                verbose = True
            elif o in ("-h", "--help"):
                usage()
                sys.exit()
            elif o in ("-s", "--server"):
                SERVER_HOST = a
            elif o in ("-i", "--channelid"):
                CHANNEL_ID = a
            else:
                assert False, "unhandled option"
        createUrlPatterns()
        run()
    except KeyboardInterrupt as e:
        print ("Quiting...")
    except getopt.GetoptError as err:
        # print help information and exit:
        print (str(err))  # will print something like "option -a not recognized"
        usage()
        sys.exit(2)
