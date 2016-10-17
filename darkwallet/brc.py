import logging
import time
import zmq
from libbitcoin import bc
from darkwallet.util import encode_hex

def hash_transaction(raw_tx):
    return bc.bitcoin_hash(raw_tx).data[::-1]

class RadarInterface:

    def __init__(self, context, settings, loop):
        self._monitored = {}

        # Create socket
        self._socket = context.zmq_context.socket(zmq.SUB)
        self._socket.connect(settings.txradar_url)
        self._socket.setsockopt(zmq.SUBSCRIBE, b"")
        loop.spawn_callback(self._listen)

        self._loop = loop
        self._cleanup_timeout = settings.txradar_cleanup_timeout
        self._schedule_cleanup()

    def _schedule_cleanup(self):
        self._loop.add_timeout(self._cleanup_timeout, self._clean_old)

    async def _listen(self):
        while True:
            _, tx_hash = await self._socket.recv_multipart()
            if tx_hash in self._monitored:
                self._notify(tx_hash)

    def _notify(self, tx_hash):
        assert tx_hash in self._monitored
        cb = self._monitored[tx_hash]
        if cb.is_expired():
            del self._monitored[tx_hash]
            return
        cb.notify(tx_hash)

    async def _clean_old(self):
        # Delete expired items.
        self._monitored = {tx_hash: notify for tx_hash, notify in
                           self._monitored.items() if not notify.is_expired()}
        self._schedule_cleanup()

    def monitor(self, tx_hash, notify):
        self._monitored[tx_hash] = notify

class NotifyCallback:

    def __init__(self, connection, expire_time):
        self._connection = connection
        self._timestamp = time.time()
        self._expire_time = expire_time
        self._count = 0

    def notify(self, tx_hash):
        response = {
            "command": "broadcast.update",
            "params": [
                encode_hex(tx_hash),
                self._count
            ]
        }
        self._connection.queue(response)
        self._count += 1

    def is_expired(self):
        if not self._connection._connected:
            return True
        time_now = time.time()
        return self._timestamp + self._expire_time < time_now

class Broadcaster:

    commands = [
        "broadcast"
    ]

    def __init__(self, context, settings, loop, client):
        self._client = client
        self._radar = RadarInterface(context, settings, loop)
        self._expire_time = settings.txradar_watch_expire_time

    @staticmethod
    def parse_params(request):
        if not request["params"]:
            logging.error("No param for broadcast specified.")
            return None
        try:
            raw_tx = bytes.fromhex(request["params"][0])
        except ValueError:
            logging.error("Bad parameter supplied for broadcast.")
            return None
        return raw_tx

    async def handle(self, request, connection):
        assert request["command"] in self.commands
        raw_tx = self.parse_params(request)
        if raw_tx is None:
            return None
        # Prepare notifier object
        tx_hash = hash_transaction(raw_tx)
        notify = NotifyCallback(connection, self._expire_time)
        self._radar.monitor(tx_hash, notify)
        # Add to txradar
        ec = await self._client.broadcast(raw_tx)
        # Response
        return {
            "id": request["id"],
            "error": ec,
            "result": [
            ]
        }

