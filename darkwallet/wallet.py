class Wallet:

    def __init__(self, client):
        self._client = client

class WalletInterfaceCallback:

    def __init__(self, client, request):
        self._client = client
        self._request = request

    def initialize(self, params):
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

class DwCreateAccount(WalletInterfaceCallback):

    def initialize(self, params):
        if len(params) != 2:
            return False
        self._account, self._password = params
        return True

    async def make_query(self):
        ec, height = await self._client.last_height()
        if ec:
            print("Error reading block height: %s" % ec)
            return ec, []
        return ec, [height]

class WalletInterface:

    _handlers = {
        "dw_create_account": DwCreateAccount
    }

    def __init__(self, client):
        self._client = client
        self._wallet = Wallet(client)

    @property
    def commands(self):
        return self._handlers.keys()

    async def handle(self, request):
        command = request["command"]
        assert command in self.commands

        handler = self._handlers[command](self._client, request)
        return await handler.query()

