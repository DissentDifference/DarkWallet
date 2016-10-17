from twisted.internet import ssl, reactor

from autobahn.twisted.websocket import WebSocketClientFactory, \
                                       WebSocketClientProtocol, \
                                       connectWS
import random
import json

conn = None
client = None

class LegacyClient:
    def __init__(self, url):
        global client
        client = self
        self.factory = ClientFactory(url, reactor=reactor)
        self.factory.connect()
    def reconnect(self):
        print "Reconnecting WebSocket"
        self.factory.connect()
    def fetch_stealth(self, *args):
        global conn
        conn.fetch_stealth(*args)

class ClientProtocol(WebSocketClientProtocol):
    _subscriptions = {}
    def make_request(self, cb, command, *args):
        new_id = str(random.randint(0,40000))
        cmd = {'command': command, 'id': new_id, 'params': args}
        self._subscriptions[new_id] = cb
        print json.dumps(cmd).encode('utf8')
        return json.dumps(cmd).encode('utf8')
    def send_request(self, cb, command, *args):
        self.sendMessage(self.make_request(cb, command, *args))
    # twisted callbacks
    def onConnect(self, request):
        global conn
        conn = self
        print("WebSocket Client connecting: {}".format(request.peer))
    def onOpen(self):
        print("WebSocket connection open.")
    def fetch_stealth(self, prefix, from_height, cb):
        self.send_request(cb, "fetch_stealth", prefix, from_height)
    def onClose(self, wasClean, code, reason):
        print("WebSocket connection closed: {}".format(reason))
        global client
        client.reconnect()
    def onMessage(self, payload, isBinary):
        if not isBinary:
            try:
                msg = json.loads(payload.decode('utf8'))
                msg_id = msg.get('id', None)
                if msg_id in self._subscriptions:
                    self._subscriptions[msg_id](msg)
            except:
                traceback.print_exc()


class ClientFactory(WebSocketClientFactory):
    protocol = ClientProtocol
    def connect(self):
        print "WEBSOCKET connecting", self.isSecure
        ## SSL client context: default
        ##
        if self.isSecure:
            contextFactory = ssl.ClientContextFactory()
        else:
            contextFactory = None
        connectWS(self, contextFactory)

