import time
import obelisk
import zmq
import threading
import config
import struct
from collections import defaultdict
from twisted.internet import reactor

def hash_transaction(raw_tx):
    return obelisk.Hash(raw_tx)[::-1]

class Radar:
    def __init__(self):
        self._monitor_tx = {}
        self._monitor_lock = threading.Lock()
        self.last_status = time.time()
        self.radar_hosts = 0
        self.issues = 0
        reactor.callInThread(self.status_loop)
        reactor.callInThread(self.feedback_loop)
        reactor.callLater(1, self.watchdog)

    def watchdog(self):
        if self.last_status + 5 < time.time():
            print "radar issues!", self.issues
            self.issues += 1
        elif not self.radar_hosts:
            print "radar has no peers!"
        else:
            self.issues = 0
        reactor.callLater(1, self.watchdog)

    def feedback_loop(self, *args):
        # feedback socket
        ctx = zmq.Context()
        socket = ctx.socket(zmq.SUB)
        socket.setsockopt(zmq.SUBSCRIBE, "")
        socket.connect(config.get("radar-feedback-url", "tcp://localhost:7678"))
        print "radar feedback channel connected"
        while True:
            msg = [socket.recv()]
            while socket.getsockopt(zmq.RCVMORE):
                msg.append(socket.recv())
            if len(msg) == 2:
                self.on_feedback_msg(*msg)
            else:
                print "bad feedback message", len(msg)

    def on_feedback_msg(self, node_id_raw, tx_hash):
        try:
            node_id = struct.unpack("<I", node_id_raw)
        except:
            print "error decoding radar feedback"
        try:
            self._new_tx(tx_hash[::-1])
        except:
            print "error sending client notifications"

    def status_loop(self, *args):
        # feedback socket
        print "connect radar feedback"
        ctx = zmq.Context()
        socket = ctx.socket(zmq.SUB)
        socket.setsockopt(zmq.SUBSCRIBE, "")
        socket.connect(config.get("radar-feedback-url", "tcp://localhost:7679"))
        print "radar status channel connected"
        while True:
            msg = socket.recv()
            nodes = 0
            try:
                nodes = struct.unpack("<Q", msg)[0]
                self.last_status = time.time()
            except:
                print "bad nodes data", msg
            if not nodes == self.radar_hosts:
                print "radar hosts", nodes
                self.radar_hosts = nodes

    def _increment_monitored_tx(self, tx_hash):
        with self._monitor_lock:
            self._monitor_tx[tx_hash][0] += 1
            return self._monitor_tx[tx_hash]

    def _new_tx(self, tx_hash):
        try:
            count, notify_callback = self._increment_monitored_tx(tx_hash)
        except KeyError:
            # This tx was not broadcasted by us.
            return
        # Percentage propagation throughout network.
        ratio = float(count) / self.radar_hosts
        # Maybe one node reports a tx back to us twice.
        # No biggie. We just cover it up, and pretend it didn't happen.
        ratio = min(ratio, 1.0)
        # Call callback to notify tx was seen
        notify_callback(ratio)

    def monitor(self, tx_hash, notify_callback):
        # Add tx to monitor list for radar
        with self._monitor_lock:
            self._monitor_tx[tx_hash] = [0, notify_callback]

    @property
    def total_connections(self):
        return self.radar_hosts
