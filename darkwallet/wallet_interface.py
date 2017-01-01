import darkwallet.wallet

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
        if len(params) != 3:
            return False
        self._account, self._password, self._use_testnet = params
        return True

    async def make_query(self):
        return await self._wallet.create_account(
            self._account, self._password, self._use_testnet)

class DwSeed(WalletInterfaceCallback):

    def initialize(self, params):
        if params:
            return False
        return True

    async def make_query(self):
        return await self._wallet.seed()

class DwRestoreAccount(WalletInterfaceCallback):

    def initialize(self, params):
        if len(params) != 4:
            return False
        self._account, self._brainwallet, \
            self._password, self._use_testnet = params
        return True

    async def make_query(self):
        return await self._wallet.restore_account(self._account,
            self._brainwallet, self._password, self._use_testnet)

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
        if len(params) != 3:
            return False
        self._dests, self._pocket, self._fee = params
        return True

    async def make_query(self):
        return await self._wallet.send(self._dests, self._pocket, self._fee)

class DwReceive(WalletInterfaceCallback):

    def initialize(self, params):
        if len(params) != 1:
            return False
        self._pocket = params[0]
        return True

    async def make_query(self):
        return await self._wallet.receive(self._pocket)

class DwStealth(WalletInterfaceCallback):

    def initialize(self, params):
        if len(params) != 1:
            return False
        self._pocket = params[0]
        return True

    async def make_query(self):
        return await self._wallet.stealth(self._pocket)

class DwGetHeight(WalletInterfaceCallback):

    def initialize(self, params):
        return not params

    async def make_query(self):
        return await self._wallet.get_height()

class DwGetSetting(WalletInterfaceCallback):

    def initialize(self, params):
        if len(params) != 1:
            return False
        self._name = params[0]
        return True

    async def make_query(self):
        return await self._wallet.get_setting(self._name)

class DwSetSetting(WalletInterfaceCallback):

    def initialize(self, params):
        if len(params) != 2:
            return False
        self._name, self._value = params
        return True

    async def make_query(self):
        return await self._wallet.set_setting(self._name, self._value)

class DwStop(WalletInterfaceCallback):

    async def make_query(self):
        await self._wallet.stop()
        return None, []

class WalletInterface:

    _handlers = {
        "dw_create_account":    DwCreateAccount,
        "dw_seed":              DwSeed,
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
        "dw_receive":           DwReceive,
        "dw_stealth":           DwStealth,
        "dw_get_height":        DwGetHeight,
        "dw_get_setting":       DwGetSetting,
        "dw_set_setting":       DwSetSetting,
        "dw_stop":              DwStop
    }

    def __init__(self, context, settings):
        self._wallet = darkwallet.wallet.Wallet(context, settings)

    @property
    def commands(self):
        return self._handlers.keys()

    async def handle(self, request):
        command = request["command"]
        assert command in self.commands

        handler = self._handlers[command](self._wallet, request)
        return await handler.query()

