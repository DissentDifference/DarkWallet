import os

import libbitcoin.server
import darkwallet.util
from libbitcoin import bc

class Account:

    def __init__(self, name, filename, password, settings, client):
        self.name = name
        self._filename = filename
        self._password = password

    def set_seed(self, seed):
        self._seed = seed

    def save(self):
        pass

    def load(self):
        pass

def create_brainwallet_seed():
    entropy = os.urandom(1024)
    return bc.create_mnemonic(entropy)

class Wallet:

    def __init__(self, settings, client):
        self._settings = settings
        self._client = client

        self._init_accounts_path()
        self._accounts = darkwallet.util.list_files(self.accounts_path)
        self._account = None

    @property
    def accounts_path(self):
        return os.path.join(self._settings.config_path, "accounts")

    def _init_accounts_path(self):
        darkwallet.util.make_sure_dir_exists(self.accounts_path)

    def account_filename(self, account_name):
        return os.path.join(self.accounts_path, account_name)

    async def create_account(self, account_name, password):
        print("create_account", account_name, password)
        if account_name in self._accounts:
            return libbitcoin.server.ErrorCode.duplicate, []

        # Create new seed
        wordlist = create_brainwallet_seed()
        seed = bc.decode_mnemonic(wordlist)

        account_filename = self.account_filename(account_name)
        # Init current account object
        self._account = Account(account_name, account_filename, password,
                                self._settings, self._client)
        self._account.set_seed(seed)
        self._account.save()
        self._accounts.append(account_name)

        return None, []

    async def restore_account(self, account, brainwallet, password):
        print("restore_account", account, brainwallet, password)
        # Create new seed
        wordlist = brainwallet.strip().split(" ")
        seed = bc.decode_mnemonic(wordlist)

        account_filename = self.account_filename(account_name)
        # Init current account object
        self._account = Account(account_name, account_filename, password,
                                self._settings, self._client)
        self._account.set_seed(seed)
        self._account.save()
        self._accounts.append(account_name)
        return None, []

    async def balance(self, pocket):
        print("balance", pocket)
        return None, []

    async def history(self, pocket):
        print("history", pocket)
        return None, []

    async def list_accounts(self):
        return None, [self._accounts.keys()]

    async def set_account(self, account_name, password):
        if account_name in self._accounts:
            return libbitcoin.server.ErrorCode.not_found, []
        # Init current account object
        self._account = Account(account_name, account_filename, password,
                                self._settings, self._client)
        self._account.load()
        return None, []

    async def delete_account(self, account_name):
        if account_name in self._accounts:
            return libbitcoin.server.ErrorCode.not_found, []
        if self._account.name == account_name:
            self._account = None
        del self._accounts[account_name]
        account_filename = self.account_filename(account_name)
        os.remove(account_filename)
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

