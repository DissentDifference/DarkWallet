import logging
import libbitcoin
from darkwallet.util import encode_hex

class BitcoinServerCallback:

    def __init__(self, client, request):
        self._client = client
        self._request = request

    def check_request(self):
        return True

    async def make_query(self):
        return None, []

    async def query(self):
        if not self.initialize(self._params):
            logging.error("Bad parameters specified: %s",
                          self._params, exc_info=True)
            return None
        ec, result = await self.make_query()
        return self._response(ec, result)

    @property
    def _request_id(self):
        return self._request["id"]
    @property
    def _params(self):
        return self._request["params"]

    def _response(self, ec, result):
        if ec is not None:
            result = []
            ec = ec.name
        return {
            "id": self._request_id,
            "error": ec,
            "result": result
        }

def decode_hash(encoded_hash):
    try:
        decoded_hash = bytes.fromhex(encoded_hash)
    except ValueError:
        return None
    if len(decoded_hash) != 32:
        return None
    return decoded_hash

def unpack_index(index):
    if type(index) == str:
        return decode_hash(index)
    elif type(index) == int:
        return index
    else:
        return None

class BsFetchLastHeight(BitcoinServerCallback):

    def initialize(self, params):
        return len(params) == 0

    async def make_query(self):
        ec, height = await self._client.last_height()
        if ec:
            return ec, []
        return ec, [height]

class BsFetchTransaction(BitcoinServerCallback):

    def initialize(self, params):
        if len(params) != 1:
            return False
        self._tx_hash = decode_hash(params[0])
        if self._tx_hash is None:
            return False
        return True

    async def make_query(self):
        ec, tx_data = await self._client.transaction(self._tx_hash)
        if ec:
            return ec, []
        tx_data = encode_hex(tx_data)
        return ec, [tx_data]

class BsFetchHistory(BitcoinServerCallback):

    def initialize(self, params):
        if len(params) != 1 and len(params) != 2:
            return False
        self._address = params[0]
        self._from_height = 0
        if len(params) == 2:
            self._from_height = params[1]
        return type(self._address) == str and type(self._from_height) == int

    async def make_query(self):
        ec, history = await self._client.history(self._address,
                                                 from_height=self._from_height)
        if ec:
            return ec, []
        result = []
        for point, height, value in history:
            if type(point) == libbitcoin.OutPoint:
                result.append({
                    "type": "output",
                    "point": point.tuple(),
                    "height": height,
                    "value": value,
                    "checksum": point.checksum()
                })
            elif type(point) == libbitcoin.InPoint:
                result.append({
                    "type": "spend",
                    "point": point.tuple(),
                    "height": height,
                    "outpoint_checksum": value
                })
        return ec, result

class BsFetchBlockHeader(BitcoinServerCallback):

    def initialize(self, params):
        if len(params) != 1:
            return False
        self._index = unpack_index(params[0])
        return True

    async def make_query(self):
        ec, header = await self._client.block_header(self._index)
        if ec:
            return ec, []
        header = encode_hex(header)
        return ec, [header]

class BsFetchBlockTransactionHashes(BitcoinServerCallback):

    def initialize(self, params):
        if len(params) != 1:
            return False
        self._index = unpack_index(params[0])
        return True

    async def make_query(self):
        ec, hashes = await self._client.block_transaction_hashes(self._index)
        if ec:
            return ec, []
        results = []
        for hash in hashes:
            results.append(encode_hex(hash))
        return ec, results

class BsFetchSpend(BitcoinServerCallback):

    def initialize(self, params):
        if len(params) != 1:
            return False
        point = params[0]
        if len(point) != 2:
            return False
        self._outpoint = libbitcoin.OutPoint()
        self._outpoint.hash = decode_hash(point[0])
        if self._outpoint.hash is None:
            return False
        self._outpoint.index = point[1]
        return type(self._outpoint.index) == int

    async def make_query(self):
        ec, spend = await self._client.spend(self._outpoint)
        if ec:
            return ec, []
        return ec, [spend.tuple()]

class BsFetchTransactionIndex(BitcoinServerCallback):

    def initialize(self, params):
        if len(params) != 1:
            return False
        self._tx_hash = decode_hash(params[0])
        if self._tx_hash is None:
            return False
        return True

    async def make_query(self):
        ec, height, index = await self._client.transaction_index(self._tx_hash)
        if ec:
            return ec, []
        return ec, [height, index]

class BsFetchBlockHeight(BitcoinServerCallback):

    def initialize(self, params):
        if len(params) != 1:
            return False
        self._block_hash = decode_hash(params[0])
        if self._block_hash is None:
            return False
        return True

    async def make_query(self):
        ec, height = await self._client.block_height(self._block_hash)
        if ec:
            return ec, []
        return ec, [height]

class BsFetchStealth(BitcoinServerCallback):

    def initialize(self, params):
        if len(params) != 1 and len(params) != 2:
            return False
        self._prefix = libbitcoin.Binary.from_string(params[0])
        if self._prefix is None:
            return False
        self._from_height = 0
        if len(params) == 2:
            self._from_height = params[1]
        return type(self._from_height) == int

    async def make_query(self):
        ec, rows = await self._client.stealth(self._prefix, self._from_height)
        if ec:
            return ec, []
        results = []
        for ephemkey, address_hash, tx_hash in rows:
            results.append({
                "ephemeral_key": encode_hex(ephemkey),
                "address_hash": encode_hex(address_hash),
                "tx_hash": encode_hex(tx_hash)
            })
        return ec, results

class BitcoinServerModule:

    _handlers = {
        "fetch_last_height":                BsFetchLastHeight,
        "fetch_transaction":                BsFetchTransaction,
        "fetch_history":                    BsFetchHistory,
        "fetch_block_header":               BsFetchBlockHeader,
        "fetch_block_transaction_hashes":   BsFetchBlockTransactionHashes,
        "fetch_spend":                      BsFetchSpend,
        "fetch_transaction_index":          BsFetchTransactionIndex,
        "fetch_block_height":               BsFetchBlockHeight,
        "fetch_stealth":                    BsFetchStealth
    }

    def __init__(self, client):
        self._client = client

    @property
    def commands(self):
        return self._handlers.keys()

    async def handle(self, request):
        command = request["command"]
        assert command in self.commands

        handler = self._handlers[command](self._client, request)
        return await handler.query()

