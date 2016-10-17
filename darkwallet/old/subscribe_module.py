import libbitcoin
import darkwallet.bs_module
from darkwallet.util import encode_hex

def make_key(prefix, connection):
    return "%s_%s" % (str(prefix), str(connection.connection_id))

class SubscriptionManager:

    def __init__(self):
        self._subscriptions = {}

    def add(self, prefix, wrapped_sub):
        key = make_key(prefix, wrapped_sub)
        self._subscriptions[key] = wrapped_sub

    def subscription_exists(self, prefix, connection):
        key = make_key(prefix, connection)
        return key in self._subscriptions

    async def delete_all(self, connection):
        for sub in self._subscriptions.values():
            if sub.connection_id == connection.connection_id:
                await sub.stop()
        self._cleanup()

    def _cleanup(self):
        # Stop all subs that are expired.
        self._subscriptions = {key: sub for key, sub in
                               self._subscriptions.items()
                               if not sub.stopped}

class SubscriptionWrapper:

    def __init__(self, base_subscription, connection, loop):
        self._base = base_subscription
        self._connection = connection
        loop.spawn_callback(self._watch)

    async def _watch(self):
        with self._base:
            while self._base.is_running():
                update = await self._base.updates()
                self._notify(update)

    def _notify(self, update):
        if update.confirmed:
            block_id = update.height, encode_hex(update.block_hash)
        else:
            block_id = None
        message = {
            "command": "subscribe.update",
            "params": [
                block_id,
                encode_hex(update.tx_data)
            ]
        }
        self._connection.queue(message)

    @property
    def stopped(self):
        return not self._base.is_running()

    async def stop(self):
        await self._base.stop()

    @property
    def connection_id(self):
        return self._connection.connection_id


def is_binary_string(prefix):
    return set(prefix).issubset(set("01"))

class BsSubscribeAddress(darkwallet.bs_module.BitcoinServerCallback):

    def __init__(self, client, request, manager, connection, loop):
        super().__init__(client, request)
        self._manager = manager
        self._connection = connection
        self._loop = loop

    def initialize(self, params):
        if len(params) != 1:
            return False
        prefix = params[0]
        if is_binary_string(prefix):
            self._prefix = libbitcoin.Binary.from_string(prefix)
        else:
            self._prefix = libbitcoin.Binary.from_address(prefix)
        return True

    async def make_query(self):
        if self._manager.subscription_exists(self._prefix, self._connection):
            ec = libbitcoin.ErrorCode.duplicate
            return ec, []
        return await self.create_new()

    async def create_new(self):
        ec, subscription = await self._client.subscribe_address(self._prefix)
        wrapped_sub = SubscriptionWrapper(subscription,
                                          self._connection, self._loop)
        self._manager.add(self._prefix, wrapped_sub)
        return ec, []

class SubscribeModule:

    _handlers = {
        "subscribe_address":                BsSubscribeAddress
    }

    def __init__(self, client, loop):
        self._client = client
        self._loop = loop
        self._manager = SubscriptionManager()

    @property
    def commands(self):
        return self._handlers.keys()

    async def handle(self, request, connection):
        command = request["command"]
        assert command in self.commands
        cls = self._handlers[command]

        handler = cls(self._client, request, self._manager,
                      connection, self._loop)

        return await handler.query()

    async def delete_all(self, connection):
        await self._manager.delete_all(connection)

