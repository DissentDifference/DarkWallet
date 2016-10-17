import time
import obelisk
import zmq
import radar
import config
import struct
from collections import defaultdict
from twisted.internet import reactor
from broadcast_connector import BroadcastConnector

def hash_transaction(raw_tx):
    return obelisk.Hash(raw_tx)[::-1]

class Broadcaster:

    def __init__(self):
        self.connector = BroadcastConnector()
        self.last_status = time.time()
        self.last_nodes = 0
        self.issues = 0
        self.notifications = defaultdict(list)
        reactor.callInThread(self.status_loop)
        reactor.callInThread(self.feedback_loop)
        reactor.callLater(1, self.watchdog)

    def watchdog(self):
        if self.last_status + 5 < time.time():
            print "broadcaster issues!", self.issues
            self.issues += 1
        else:
            self.issues = 0
        reactor.callLater(1, self.watchdog)

    def feedback_loop(self, *args):
        # feedback socket
        ctx = zmq.Context()
        socket = ctx.socket(zmq.SUB)
        socket.setsockopt(zmq.SUBSCRIBE, "")
        socket.connect(config.get("broadcaster-feedback-url", "tcp://localhost:9110"))
        print "brc feedback channel connected"
        while True:
            msg = [socket.recv()]
            while socket.getsockopt(zmq.RCVMORE):
                msg.append(socket.recv())
                print "feedback msg"
            if len(msg) == 3:
                self.on_feedback_msg(*msg)
            else:
                print "bad feedback message", len(msg)

    def on_feedback_msg(self, hash, num, error):
        try:
            num = struct.unpack("<Q", num)[0]
            error = struct.unpack("<Q", error)[0]
            #print "error", hash.encode('hex'), num, error
        except:
            print "error decoding brc feedback"
        try:
            # trigger notifications
            for notify in self.notifications[hash]:
                notify(num, 'brc-stats', num == 0)
            del self.notifications[hash]
        except:
            print "error sending client notifications"

    def status_loop(self, *args):
        # feedback socket
        print "connect brc feedback"
        ctx = zmq.Context()
        socket = ctx.socket(zmq.SUB)
        socket.setsockopt(zmq.SUBSCRIBE, "")
        socket.connect(config.get("broadcaster-feedback-url", "tcp://localhost:9112"))
        print "brc status channel connected"
        while True:
            msg = socket.recv()
            nodes = 0
            try:
                nodes = struct.unpack("<Q", msg)[0]
                self.last_status = time.time()
            except:
                print "bad nodes data", msg
            if not nodes == self.last_nodes:
                print "brc hosts", nodes
                self.last_nodes = nodes

    def broadcast(self, raw_tx, notify):
        tx_hash = hash_transaction(raw_tx)
        self.notifications[tx_hash].append(notify)
        def cb(txhash, error, result):
            if error or not result:
                notify(0, 'brc', 'Broadcaster could not propagate')
            else:
                notify(result, 'brc')
        self.connector.broadcast(raw_tx, cb)


class NotifyCallback:

    def __init__(self, socket_handler, request_id):
        self._handler = socket_handler
        self._request_id = request_id

    def __call__(self, count, type='radar', error=None):
        response = {
            "id": self._request_id,
            "error": error or None,
            "result": [count, type]
        }
        self._handler.queue(response)

class BroadcastHandler:

    def __init__(self):
        self._brc = Broadcaster()
        self._radar = radar.Radar()

    def handle_request(self, socket_handler, request):
        if request["command"] != "broadcast_transaction":
            return False
        if not request["params"]:
            logging.error("No param for broadcast specified.")
            return True
        raw_tx = request["params"][0].decode("hex")
        request_id = request["id"]
        # Prepare notifier object
        notify = NotifyCallback(socket_handler, request_id)
        # Broadcast...
        print "BROADCAT"
        self._brc.broadcast(raw_tx, notify)
        # And monitor.
        print "BROADCAST"
        tx_hash = hash_transaction(raw_tx)
        print "MONITOR", tx_hash
        self._radar.monitor(tx_hash, notify)
        notify(0.0)
        return True

