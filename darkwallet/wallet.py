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

class Account:

    def __init__(self, name, filename, password, settings, client):
        self.name = name
        self._filename = filename
        self._password = bytes(password, "utf-8")

    def set_seed(self, seed):
        self._seed = seed

    def save(self):
        wallet_info = self._save_values()
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
        self._load_values(wallet_info)
        return True

    def _save_values(self):
        return {
            "seed": self._seed.encode_base16()
        }

    def _load_values(self, wallet_info):
        self._seed = bc.LongHash.from_string(wallet_info["seed"])

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
        self._account_names.append(account_name)

        return None, []

    async def restore_account(self, account, brainwallet, password):
        print("restore_account", account, brainwallet, password)
        # Create new seed
        wordlist = brainwallet.strip().split(" ")
        if not bc.validate_mnemonic(wordlist):
            return ErrorCode.invalid_brainwallet, []
        seed = bc.decode_mnemonic(wordlist)

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
            return libbitcoin.server.ErrorCode.not_found, []
        account_filename = self.account_filename(account_name)
        # Init current account object
        self._account = Account(account_name, account_filename, password,
                                self._settings, self._client)
        if not self._account.load():
            return ErrorCode.wrong_password, []
        return None, []

    async def delete_account(self, account_name):
        if not account_name in self._account_names:
            return libbitcoin.server.ErrorCode.not_found, []
        if self._account.name == account_name:
            self._account = None
        del self._account_names[account_name]
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

