class Wallet:

    def __init__(self, client):
        self._client = client

    async def create_account(self, account, password):
        print("create_account", account, password)
        return None, [110]
        #ec, height = await self._client.last_height()
        #if ec:
            #print("Error reading block height: %s" % ec)
            #return ec, []
        #return ec, [height]

    async def restore_account(self, account, brainwallet, password):
        print("restore_account", account, brainwallet, password)
        return None, []

    async def balance(self, pocket):
        print("balance", pocket)
        return None, []

    async def history(self, pocket):
        print("history", pocket)
        return None, []

    async def list_accounts(self):
        print("list_accounts")
        return None, []

    async def set_account(self, account, password):
        print("set_account", account, password)
        return None, []

    async def delete_account(self, account):
        print("delete_account", account)
        return None, []

    async def list_pockets(self):
        print("list_pockets")
        return None, []

    async def create_pocket(self, pocket):
        print("create_pocket", pocket)
        return None, []

    async def delete_pocket(self, pocket):
        print("delete_pocket", pocket)
        return None, []

    async def send(self, dests, from_pocket=None):
        print("send", dests, from_pocket)
        return None, []

    async def receive(self, pocket):
        print("receive", pocket)
        return None, []

class WalletInterfaceCallback:

    def __init__(self, wallet, request):
        self._wallet = wallet
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
        return await self._wallet.create_account(
            self._account, self._password)

class DwRestoreAccount(WalletInterfaceCallback):

    def initialize(self, params):
        if len(params) != 3:
            return False
        self._account, self._brainwallet, self._password = params
        return True

    async def make_query(self):
        return await self._wallet.restore_account(
            self._account, self._brainwallet, self._password)

class DwBalance(WalletInterfaceCallback):

    def initialize(self, params):
        if len(params) != 1:
            return False
        self._pocket = params[0]
        return True

    async def make_query(self):
        return await self._wallet.balance(self._pocket)

class DwHistory(WalletInterfaceCallback):

    def initialize(self, params):
        if len(params) != 1:
            return False
        self._pocket = params[0]
        return True

    async def make_query(self):
        return await self._wallet.history(self._pocket)

class DwListAccounts(WalletInterfaceCallback):

    def initialize(self, params):
        return not params

    async def make_query(self):
        return await self._wallet.list_accounts()

class DwSetAccount(WalletInterfaceCallback):

    def initialize(self, params):
        if len(params) != 2:
            return False
        self._account, self._password = params
        return True

    async def make_query(self):
        return await self._wallet.set_account(self._account, self._password)

class DwDeleteAccount(WalletInterfaceCallback):

    def initialize(self, params):
        if len(params) != 1:
            return False
        self._account = params[0]
        return True

    async def make_query(self):
        return await self._wallet.delete_account(self._account)

class DwListPockets(WalletInterfaceCallback):

    def initialize(self, params):
        return not params

    async def make_query(self):
        return await self._wallet.list_pockets()

class DwCreatePocket(WalletInterfaceCallback):

    def initialize(self, params):
        if len(params) != 1:
            return False
        self._pocket = params[0]
        return True

    async def make_query(self):
        return await self._wallet.create_pocket(self._pocket)

class DwDeletePocket(WalletInterfaceCallback):

    def initialize(self, params):
        if len(params) != 1:
            return False
        self._pocket = params[0]
        return True

    async def make_query(self):
        return await self._wallet.delete_pocket(self._pocket)

class DwSend(WalletInterfaceCallback):

    def initialize(self, params):
        if len(params) != 2:
            return False
        self._dests, self._pocket = params
        return True

    async def make_query(self):
        return await self._wallet.send(self._dests, self._pocket)

class DwReceive(WalletInterfaceCallback):

    def initialize(self, params):
        if len(params) != 1:
            return False
        self._pocket = params[0]
        return True

    async def make_query(self):
        return await self._wallet.receive(self._pocket)

class WalletInterface:

    _handlers = {
        "dw_create_account":    DwCreateAccount,
        "dw_restore_account":   DwRestoreAccount,
        "dw_balance":           DwBalance,
        "dw_history":           DwHistory,
        "dw_list_accounts":     DwListAccounts,
        "dw_set_account":       DwSetAccount,
        "dw_delete_account":    DwDeleteAccount,
        "dw_list_pockets":      DwListPockets,
        "dw_create_pocket":     DwCreatePocket,
        "dw_delete_pocket":     DwDeletePocket,
        "dw_send":              DwSend,
        "dw_receive":           DwReceive
    }

    def __init__(self, client):
        self._wallet = Wallet(client)

    @property
    def commands(self):
        return self._handlers.keys()

    async def handle(self, request):
        command = request["command"]
        assert command in self.commands

        handler = self._handlers[command](self._wallet, request)
        return await handler.query()

