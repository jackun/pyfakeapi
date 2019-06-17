import os
import re
import urllib
from io import StringIO, BytesIO
import json
import random, string

def _json_default(obj):
    # filter out fields that start with '_'
    return {k: obj.__dict__[k] for k in obj.__dict__ if k[0] != "_"}

def _encoded_bytesio(encoding='utf-8'):
    b = BytesIO()
    func = b.write
    def wrapped_write(s, *args, **kwargs):
        return func(s.encode(encoding), *args, **kwargs)
    b.write = wrapped_write
    return b

def get_json(obj):
    return json.dumps(obj, default=_json_default)

class API:

    def do_channel(self, request, channelid, **kwargs):
        """
          /channel/{channelid}
        """
        f = _encoded_bytesio()
        s = {}
        hdrs = {}
        f.write("""<html><body>Nuffin here\n""")
        request.send_html(f, hdrs)

    
    def do_users_channels(self, request, **kwargs):
        """
          /users/self/channels.json?detail_level=broadcaster
        """
        print("Detail level:", kwargs.get('detail_level'))
        print ("Auth:", request.headers.get('Authorization'))
        dlevel = kwargs.get('detail_level')
        if dlevel and dlevel == "broadcaster":
            pass

        f = _encoded_bytesio()
        s = {}
        hdrs = {}
        s = {
            "channels": {
                "1234567890": {
                    "id": "1234567890",
                    "title": "My Stream",
                    "url": "http://www.ustream.tv/channel/MyChannel",
                    "tiny_url": "https://www.ustream.tv/channel/MyChannel",
                    "broadcast_urls": [
                        "rtmp://" + kwargs.get('host', 'localhost') + "/live/broadcaster",
                    ],
                    "status": "offline",
                    "description": None,
                    "owner": {
                        "id": "12345678980",
                        "username": "blaablaablaa",
                        "picture": "http://static-cdn1.ustream.tv/images/defaults/user_48x48:3.png"
                    },
                    "authority": {
                        "reason": "own"
                    },
                    "picture": {
                        "90x90": "http://static-cdn1.ustream.tv/images/defaults/channel_90x90:4.png",
                        "66x66": "http://static-cdn1.ustream.tv/images/defaults/channel_66x66:4.png",
                        "48x48": "http://static-cdn1.ustream.tv/images/defaults/channel_48x48:4.png"
                    },
                    "default": True
                }
            },
            "paging": {
                "actual": {
                    "href": "http://api.ustream.tv/users/self/channels.json?detail_level=broadcaster&p=1"
                }
            }
        }
        f.write(get_json(s))
        request.send_json(f, hdrs)
