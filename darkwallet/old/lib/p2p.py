import sys
import json
from collections import defaultdict

import pyelliptic as ec

from zmq.eventloop import ioloop, zmqstream
import zmq
from multiprocessing import Process
from threading import Thread
#ioloop.install()
import traceback
import darkwallet.lib.network_util as network_util

# Default port
DEFAULT_PORT=8889

# Get some command line pars
MY_IP = "127.0.0.1"


# Connection to one peer
class PeerConnection(object):
    def __init__(self, transport, address):
        # timeout in seconds
        self._timeout = 10
        self._address = address
        self._transport = transport

    def create_socket(self):
        self._ctx = zmq.Context()
        self._socket = self._ctx.socket(zmq.REQ)
        self._socket.connect(self._address)

    def cleanup_socket(self):
        self._socket.close()

    def send(self, data):
        self.send_raw(json.dumps(data))

    def send_raw(self, serialized):
        Process(target=self._send_raw, args=(serialized,)).start()

    def _send_raw(self, serialized):
        self.create_socket()

        self._socket.send_string(serialized, zmq.NOBLOCK)

        poller = zmq.Poller()
        poller.register(self._socket, zmq.POLLIN)
        if poller.poll(self._timeout * 1000):
            msg = self._socket.recv()
            self.on_message(msg)
            self.cleanup_socket()

        else:
            self._transport.log("Peer " + self._address + " timed out.")
            self.cleanup_socket()
            self._transport.remove_peer(self._address)

    def on_message(self, msg):
        print("message received!", msg)

    def closed(self, *args):
        print(" - peer disconnected")

# Transport layer manages a list of peers
class TransportLayer(object):
    def __init__(self, port=DEFAULT_PORT, my_ip=MY_IP, net_ip=None):
        print("init as " + my_ip)
        if not net_ip:
          net_ip = my_ip
        self._peers = {}
        self._callbacks = defaultdict(list)
        self._id = my_ip[-1] # hack for logging
        self._port = port
        self._uri = 'tcp://%s:%s' % (my_ip, self._port)
        self._neturi = 'tcp://%s:%s' % (net_ip, self._port)

    def add_callback(self, section, callback):
        self._callbacks[section].append(callback)

    def trigger_callbacks(self, section, *data):
        for cb in self._callbacks[section]:
            cb(*data)
        if not section == 'all':
            for cb in self._callbacks['all']:
                cb(*data)

    def get_profile(self):
        return {'type': 'hello', 'uri': self._uri}

    def join_network(self, seeds=[]):
        self.listen()
        for seed in seeds:
            self.init_peer({'uri': seed})

    def listen(self):
        thread = Thread(target=self._listen)
        thread.daemon = True
        thread.start()

    def _listen(self):
        self.log("init server %s" % self._uri)
        self._ctx = zmq.Context()
        self._socket = self._ctx.socket(zmq.REP)
        self._socket.bind(self._neturi)
        while True:
            try:
                message = self._socket.recv()
            except:
                message = None
            if message:
                self.on_raw_message(message)
                self._socket.send(json.dumps({'type': "ok"}))

    def closed(self, *args):
        print("client left")

    def init_peer(self, msg):
        uri = msg['uri']
        self.log("init peer %s" %  msg)
        if not uri in self._peers:
            self._peers[uri] = PeerConnection(uri, self)

    def remove_peer(self, uri):
        self.log("Removing peer " + uri )
        del self._peers[uri]

        #self.log("Peers " + str(self._peers) )

    def log(self, msg, pointer='-'):
        print(" %s [%s] %s" % (pointer, self._id, msg))

    def send(self, data, send_to=None, secure=False):
        self.log("sending %s..." % data.keys())
        # directed message
        if send_to:
            for peer in self._peers.values():
                if peer._pub == send_to:
                    peer.send(data)
                    return
            print("peer not found!", send_to, self._myself.get_pubkey())
            return
        # broadcast
        for peer in self._peers.values():
            try:
                if peer._pub:
                    peer.send(data)
                elif not secure:
                    serialized = json.dumps(data)
                    peer.send_raw(serialized)
            except:
                print("error sending over peer!")
                traceback.print_exc()

    def on_message(self, msg):
        # here goes the application callbacks
        # we get a "clean" msg which is a dict holding whatever
        self.trigger_callbacks(msg.get('type'), msg)

    def on_raw_message(self, serialized):
        self.log("connected " +str(len(serialized)))
        try:
            msg = json.loads(serialized[0])
        except:
            self.log("incorrect msg! " + serialized)
            return

        msg_type = msg.get('type')
        if msg_type == 'hello' and msg.get('uri'):
            self.init_peer(msg)
        else:
            self.on_message(msg)

    def valid_peer_uri(self, uri):
        try:
            [self_protocol, self_addr, self_port] = \
                network_util.uri_parts(self._uri)
            [other_protocol, other_addr, other_port] = \
                network_util.uri_parts(uri)
        except RuntimeError:
            return False

        if not network_util.is_valid_protocol(other_protocol) \
                or not network_util.is_valid_port(other_port) \
                or not network_util.is_valid_ip_address(other_addr):
            return False

        if network_util.is_private_ip_address(self_addr):
            if not network_util.is_private_ip_address(other_addr):
                self.log('Trying to connect to external network with a private ip address.')
        else:
            if network_util.is_private_ip_address(other_addr):
                return False

        return True
