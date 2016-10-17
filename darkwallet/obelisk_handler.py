from twisted.internet import reactor

import logging
import obelisk

class ObeliskCallbackBase(object):

    def __init__(self, handler, request_id, client, legacy_server):
        self._handler = handler
        self._request_id = request_id
        self._client = client
        self._legacy_server = legacy_server

    def __call__(self, *args):
        assert len(args) > 1
        error = args[0]
        assert error is None or type(error) == str
        result = self.translate_response(args[1:])
        response = {
            "id": self._request_id,
            "error": error,
            "result": result
        }
        self._handler.queue_response(response)

    def call_method(self, method, params):
        method(*params, cb=self)

    def call_client_method(self, method_name, params):
        method = getattr(self._client, method_name)
        self.call_method(method, params)

    def translate_arguments(self, params):
        return params

    def translate_response(self, result):
        return result

# Utils used for decoding arguments.

def check_params_length(params, length):
    if len(params) != length:
        raise ValueError("Invalid parameter list length")

def decode_hash(encoded_hash):
    decoded_hash = encoded_hash.decode("hex")
    if len(decoded_hash) != 32:
        raise ValueError("Not a hash")
    return decoded_hash

def unpack_index(index):
    if type(index) == unicode:
        index = str(index)
    if type(index) != str and type(index) != int:
        raise ValueError("Unknown index type")
    if type(index) == str:
        index = index.decode("hex")
        if len(index) != 32:
            raise ValueError("Invalid length for hash index")
    return index

# The actual callback specialisations.

class ObFetchLastHeight(ObeliskCallbackBase):

    def translate_response(self, result):
        assert len(result) == 1
        return result

class ObFetchTransaction(ObeliskCallbackBase):

    def translate_arguments(self, params):
        check_params_length(params, 1)
        tx_hash = decode_hash(params[0])
        return (tx_hash,)

    def translate_response(self, result):
        assert len(result) == 1
        tx = result[0].encode("hex")
        return (tx,)

class ObUnsubscribe(ObeliskCallbackBase):
    def translate_arguments(self, params):
        check_params_length(params, 1)
        address = params[0]
        cb = None
        if address in self._handler._subscriptions['obelisk']:
            cb = self._handler._subscriptions['obelisk'][address]
            del self._handler._subscriptions['obelisk'][address]
        return (address, cb)

class ObSubscribe(ObeliskCallbackBase):

    def __call__(self, err, data):
        if self._initial:
            # only notify the client on initial subscription, not renew
            ObeliskCallbackBase.__call__(self, err, data)
            self._initial = False

        # schedule renew for subscription
        if self._handler._connected:
            if not self._address in self._handler._subscriptions['obelisk']:
                self._handler._subscriptions['obelisk'][self._address] = self.callback_update
            reactor.callLater(120, self.renew)

    def renew(self, *args):
        if self._handler._connected:
            self.call_client_method('renew_address', [self._address])

    def translate_arguments(self, params):
        # this gets called only on the initial invokation to subscribe.
        check_params_length(params, 1)
        self._address = params[0]
        self._initial = True
        return params[0], self.callback_update

    def callback_update(self, address_version, address_hash,
                        height, block_hash, tx):
        address = obelisk.bitcoin.hash_160_to_bc_address(
            address_hash, address_version)

        response = {
            "type": "update",
            "address": address,
            "height": height,
            "block_hash": block_hash.encode('hex'),
            "tx": tx.encode("hex")
        }
        try:
            # self._socket.write_message(json.dumps(response))
            self._handler.queue_response(response)
        except:
            logging.error("Error sending message", exc_info=True)


class ObFetchHistory(ObeliskCallbackBase):

    def call_method(self, method, params):
        assert len(params) == 2
        address, from_height = params
        method(address, self, from_height)

    def translate_arguments(self, params):
        if len(params) != 1 and len(params) != 2:
            raise ValueError("Invalid parameter list length")
        address = params[0]
        if len(params) == 2:
            from_height = params[1]
        else:
            from_height = 0
        return (address, from_height)

    def translate_response(self, result):
        assert len(result) == 1
        history = []
        for row in result[0]:
            o_hash, o_index, o_height, value, s_hash, s_index, s_height = row
            o_hash = o_hash.encode("hex")
            if s_hash is not None:
                s_hash = s_hash.encode("hex")
            history.append(
                (o_hash, o_index, o_height, value, s_hash, s_index, s_height))
        return (history,)

class ObFetchBlockHeader(ObeliskCallbackBase):

    def translate_arguments(self, params):
        check_params_length(params, 1)
        index = unpack_index(params[0])
        return (index,)

    def translate_response(self, result):
        assert len(result) == 1
        header = result[0].encode("hex")
        return (header,)

class ObFetchBlockTransactionHashes(ObeliskCallbackBase):

    def translate_arguments(self, params):
        check_params_length(params, 1)
        index = unpack_index(params[0])
        return (index,)

    def translate_response(self, result):
        assert len(result) == 1
        tx_hashes = []
        for tx_hash in result[0]:
            assert len(tx_hash) == 32
            tx_hashes.append(tx_hash.encode("hex"))
        return (tx_hashes,)

class ObFetchSpend(ObeliskCallbackBase):

    def translate_arguments(self, params):
        check_params_length(params, 1)
        if len(params[0]) != 2:
            raise ValueError("Invalid outpoint")
        outpoint = obelisk.models.OutPoint()
        outpoint.hash = decode_hash(params[0][0])
        outpoint.index = params[0][1]
        return (outpoint,)

    def translate_response(self, result):
        assert len(result) == 1
        outpoint = result[0]
        outpoint = (outpoint.hash.encode("hex"), outpoint.index)
        return (outpoint,)

class ObFetchTransactionIndex(ObeliskCallbackBase):

    def translate_arguments(self, params):
        check_params_length(params, 1)
        tx_hash = decode_hash(params[0])
        return (tx_hash,)

    def translate_response(self, result):
        assert len(result) == 2
        blk_height, tx_offset = result
        return blk_height, tx_offset

class ObFetchBlockHeight(ObeliskCallbackBase):

    def translate_arguments(self, params):
        check_params_length(params, 1)
        blk_hash = decode_hash(params[0])
        return (blk_hash,)

class ObFetchStealth(ObeliskCallbackBase):

    def on_stealth_response(self, msg):
        print "Websocket stealth response"
        self._handler.queue_response(msg)

    def call_client_method(self, method_name, params):
        assert len(params) == 2
        prefix, from_height = params
        if prefix == 0 or prefix == [0]:
            prefix = [0, 0]
 
        self._legacy_server.fetch_stealth(prefix, from_height, self.on_stealth_response)

    def translate_arguments(self, params):
        if len(params) != 1 and len(params) != 2:
            raise ValueError("Invalid parameter list length")
        prefix = params[0]
        if len(params) == 2:
            from_height = params[1]
        else:
            from_height = 0
        return (prefix, from_height)


class ObFetchStealth2(ObeliskCallbackBase):
    def call_client_method(self, method_name, params):
        ObeliskCallbackBase.call_client_method(self, "fetch_stealth", params)

    def call_method(self, method, params):
        assert len(params) == 2
        prefix, from_height = params
        # Workaround for bug in earlier version of Darkwallet.
        if prefix[0] == 0:
            prefix = [0]
        # Workaround for difference in api among libbitcoin versions
        if prefix == [0,0]:
            prefix = [0]
        method(prefix, self, from_height)

    def translate_arguments(self, params):
        if len(params) != 1 and len(params) != 2:
            raise ValueError("Invalid parameter list length")
        prefix = params[0]
        if len(params) == 2:
            from_height = params[1]
        else:
            from_height = 0
        return (prefix, from_height)

    def translate_response(self, result):
        assert len(result) == 1
        stealth_results = []
        for ephemkey, address, tx_hash in result[0]:
            stealth_results.append(
                (ephemkey[::-1].encode("hex"), obelisk.bitcoin.hash_160_to_bc_address(address[::-1]), tx_hash.encode("hex")))
        return (stealth_results,)



class ObDisconnectClient(ObeliskCallbackBase):
    def call_client_method(self, method_name, params):
        for address in self._handler._subscriptions['obelisk']:
            self._client.unsubscribe_address(address, self._handler._subscriptions['obelisk'][address])
            # TODO: could also unsubscribe other callbacks from this client

class ObeliskHandler:

    handlers = {
        "fetch_last_height":                ObFetchLastHeight,
        "fetch_transaction":                ObFetchTransaction,
        "fetch_history":                    ObFetchHistory,
        "fetch_block_header":               ObFetchBlockHeader,
        "fetch_block_transaction_hashes":   ObFetchBlockTransactionHashes,
        "fetch_spend":                      ObFetchSpend,
        "fetch_transaction_index":          ObFetchTransactionIndex,
        "fetch_block_height":               ObFetchBlockHeight,
        "fetch_stealth":                    ObFetchStealth,
        "fetch_stealth2":                   ObFetchStealth2,
        # Address stuff
        "renew_address":                    ObSubscribe,
        "subscribe_address":                ObSubscribe,
        "unsubscribe_address":              ObUnsubscribe,
        "disconnect_client":                ObDisconnectClient
    }

    def __init__(self, client, legacy_server):
        self._client = client
        self._legacy_server = legacy_server

    def handle_request(self, socket_handler, request):
        command = request["command"]
        if command not in self.handlers:
            return False

        params = request["params"]
        # Create callback handler to write response to the socket.
        handler = self.handlers[command](socket_handler, request["id"], self._client, self._legacy_server)
        try:
            params = handler.translate_arguments(params)
        except Exception as exc:
            logging.error("Bad parameters specified: %s", exc, exc_info=True)
            return True
        handler.call_client_method(request["command"], params)
        return True

