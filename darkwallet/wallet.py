import os.path

import darkwallet.util

class Account:

    def __init__(self, settings, client):
        pass

class Wallet:

    def __init__(self, settings, client):
        self._settings = settings
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

