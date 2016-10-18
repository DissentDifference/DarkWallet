import enum
import json
import os

import libbitcoin.server
import darkwallet.util
from libbitcoin import bc
from darkwallet import sodium

def write_json(filename, json_object):
    open(filename, "w").write(json.dumps(json_object))

def read_json(filename):
    return json.loads(open(filename).read())

class ErrorCode(enum.Enum):

    wrong_password = 1
    invalid_brainwallet = 2
    no_active_account_set = 3
    duplicate = 4
    not_found = 5

class Account:

    def __init__(self, name, filename, password, settings, client):
        self.name = name
        self._filename = filename
        self._password = bytes(password, "utf-8")
        self._pockets = {}
        self._settings = settings
        self._client = client

    def set_seed(self, seed):
        self._seed = seed
        self._root_key = bc.HdPrivate.from_seed(self._seed,
                                                bc.HdPrivate.mainnet)

    def save(self):
        wallet_info = self._save_values()
        print("Saving:", json.dumps(wallet_info, indent=2))
        message = bytes(json.dumps(wallet_info), "utf-8")
        salt, nonce, ciphertext = sodium.encrypt(message, self._password)
        encrypted_wallet_info = {
            "encrypted_wallet": ciphertext.hex(),
            "salt": salt.hex(),
            "nonce": nonce.hex()
        }
        write_json(self._filename, encrypted_wallet_info)

    def load(self):
        encrypted_wallet_info = read_json(self._filename)
        salt, nonce, ciphertext = (
            bytes.fromhex(encrypted_wallet_info["salt"]),
            bytes.fromhex(encrypted_wallet_info["nonce"]),
            bytes.fromhex(encrypted_wallet_info["encrypted_wallet"])
        )
        message = sodium.decrypt(salt, nonce, ciphertext, self._password)
        if message is None:
            return False
        message = str(message, "ascii")
        wallet_info = json.loads(message)
        print("Loading:", json.dumps(wallet_info, indent=2))
        self._load_values(wallet_info)
        return True

    def _save_values(self):
        pockets = {}
        for pocket_name, pocket in self._pockets.items():
            pockets[pocket_name] = pocket.serialize()
        return {
            "seed": self._seed.hex(),
            "pockets": pockets
        }

    def _load_values(self, wallet_info):
        seed = bytes.fromhex(wallet_info["seed"])
        self.set_seed(seed)
        for pocket_name, pocket_values in wallet_info["pockets"].items():
            pocket = Pocket.from_json(pocket_values,
                                      self._settings, self._client)
            self._pockets[pocket_name] = pocket

    def list_pockets(self):
        return list(self._pockets.keys())

    def create_pocket(self, pocket_name):
        if pocket_name in self._pockets:
            return ErrorCode.duplicate
        index = len(self._pockets)
        key = self._root_key.derive_private(index + bc.hd_first_hardened_key)
        pocket = Pocket(key, index, self._settings, self._client)
        pocket.initialize()
        self._pockets[pocket_name] = pocket
        self.save()
        return None

    def delete_pocket(self, pocket_name):
        if pocket_name not in self._pockets:
            return ErrorCode.not_found
        del self._pockets[pocket_name]
        self.save()
        return None

class Pocket:

    def __init__(self, main_key, index, settings, client):
        self._main_key = main_key
        self._index = index
        self._settings = settings
        self._client = client

    @classmethod
    def from_json(cls, values, settings, client):
        key = bc.HdPrivate.from_string(values["main_key"])
        index = values["index"]
        pocket = cls(key, index, settings, client)
        pocket._keys = [bc.HdPrivate.from_string(key_str)
                        for key_str in values["keys"]]
        return pocket

    def initialize(self):
        # Generate gap_limit (default is 5) new keys
        self._keys = [
            self._main_key.derive_private(i + bc.hd_first_hardened_key)
            for i in range(5)
        ]

    def serialize(self):
        keys = [key.encoded() for key in self._keys]
        return {
            "main_key": self._main_key.encoded(),
            "index": self._index,
            "keys": keys
        }

def create_brainwallet_seed():
    entropy = os.urandom(1024)
    return bc.create_mnemonic(entropy)

class Wallet:

    def __init__(self, settings, client):
        self._settings = settings
        self._client = client

        self._init_accounts_path()
        self._account_names = darkwallet.util.list_files(self.accounts_path)
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
        if account_name in self._account_names:
            return ErrorCode.duplicate, []

        # Create new seed
        wordlist = create_brainwallet_seed()
        seed = bc.decode_mnemonic(wordlist).data

        account_filename = self.account_filename(account_name)
        # Init current account object
        self._account = Account(account_name, account_filename, password,
                                self._settings, self._client)
        self._account.set_seed(seed)
        self._account.save()
        self._account_names.append(account_name)

        return None, []

    async def restore_account(self, account, brainwallet, password):
        print("restore_account", account, brainwallet, password)
        # Create new seed
        wordlist = brainwallet.strip().split(" ")
        if not bc.validate_mnemonic(wordlist):
            return ErrorCode.invalid_brainwallet, []
        seed = bc.decode_mnemonic(wordlist).data

        account_filename = self.account_filename(account_name)
        # Init current account object
        self._account = Account(account_name, account_filename, password,
                                self._settings, self._client)
        self._account.set_seed(seed)
        self._account.save()
        self._account_names.append(account_name)
        return None, []

    async def balance(self, pocket):
        print("balance", pocket)
        return None, []

    async def history(self, pocket):
        print("history", pocket)
        return None, []

    async def list_accounts(self):
        account_name = None if self._account is None else self._account.name
        return None, [account_name, self._account_names]

    async def set_account(self, account_name, password):
        if not account_name in self._account_names:
            return ErrorCode.not_found, []
        account_filename = self.account_filename(account_name)
        # Init current account object
        self._account = Account(account_name, account_filename, password,
                                self._settings, self._client)
        if not self._account.load():
            return ErrorCode.wrong_password, []
        return None, []

    async def delete_account(self, account_name):
        if not account_name in self._account_names:
            return ErrorCode.not_found, []
        if self._account.name == account_name:
            self._account = None
        del self._account_names[account_name]
        account_filename = self.account_filename(account_name)
        os.remove(account_filename)
        return None, []

    async def list_pockets(self):
        if self._account is None:
            return ErrorCode.no_active_account_set, []
        return None, [self._account.list_pockets()]

    async def create_pocket(self, pocket):
        if self._account is None:
            return ErrorCode.no_active_account_set, []
        return self._account.create_pocket(pocket), []

    async def delete_pocket(self, pocket):
        if self._account is None:
            return ErrorCode.no_active_account_set, []
        return self._account.delete_pocket(pocket), []

    async def send(self, dests, from_pocket=None):
        if self._account is None:
            return ErrorCode.no_active_account_set, []
        print("send", dests, from_pocket)
        return None, []

    async def receive(self, pocket):
        if self._account is None:
            return ErrorCode.no_active_account_set, []
        print("receive", pocket)
        return None, []

