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

    def __init__(self, name, filename, password, context, settings):
        self.name = name
        self._filename = filename
        self._password = bytes(password, "utf-8")
        self._pockets = {}
        self._context = context
        self._settings = settings

    def brainwallet_wordlist(self):
        return self._wordlist

    def set_seed(self, seed, wordlist, testnet):
        self._seed = seed
        self._wordlist = wordlist
        self.testnet = testnet
        prefixes = bc.HdPrivate.mainnet
        if self.testnet:
            prefixes = bc.HdPrivate.testnet
        self._root_key = bc.HdPrivate.from_seed(self._seed, prefixes)

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
            "worldlist": self._worldlist,
            "pockets": pockets,
            "testnet": self.testnet
        }

    def _load_values(self, wallet_info):
        seed = bytes.fromhex(wallet_info["seed"])
        wordlist = wallet_info["worldlist"]
        testnet = wallet_info["testnet"]
        self.set_seed(seed, wordlist, testnet)
        for pocket_name, pocket_values in wallet_info["pockets"].items():
            pocket = Pocket.from_json(pocket_values, self._settings, self)
            self._pockets[pocket_name] = pocket

    def start(self):
        client_settings = libbitcoin.server.ClientSettings()
        client_settings.query_expire_time = self._settings.query_expire_time
        client_settings.socks5 = self._settings.socks5
        url = self._settings.url
        if self.testnet:
            url = self._settings.testnet_url
        self.client = self._context.Client(url, client_settings)

    def spawn_scan(self):
        for pocket in self._pockets.values():
            self._context.spawn(pocket.scan)

    def list_pockets(self):
        return list(self._pockets.keys())

    def create_pocket(self, pocket_name):
        if pocket_name in self._pockets:
            return ErrorCode.duplicate
        index = len(self._pockets)
        key = self._root_key.derive_private(index + bc.hd_first_hardened_key)
        pocket = Pocket(key, index, self._settings, self)
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

    @property
    def all_addresses(self):
        all_addresses = []
        for pocket in self._pockets.values():
            all_addresses.extend(pocket.addresses)
        return all_addresses

    def receive(self, pocket_name=None):
        if pocket_name is not None and pocket_name not in self._pockets:
            return ErrorCode.not_found, []
        if pocket_name is None:
            return None, [self.all_addresses]
        return None, [self._pockets[pocket_name].addresses]

    @property
    def total_balance(self):
        return sum(pocket.balance() for pocket in self._pockets.values())

    def balance(self, pocket_name=None):
        if pocket_name is not None and pocket_name not in self._pockets:
            return ErrorCode.not_found, []
        if pocket_name is None:
            return None, [self.total_balance]
        return None, [self._pockets[pocket_name].balance()]

    @property
    def combined_history(self):
        result = []
        for pocket in self._pockets.values():
            result.extend(pocket.history())
        def get_key(item):
            return item[2]
        result.sort(key=get_key)
        return result

    def history(self, pocket_name=None):
        if pocket_name is not None and pocket_name not in self._pockets:
            return ErrorCode.not_found, []
        if pocket_name is None:
            # Most recent history from all pockets
            return None, self.combined_history
        return None, self._pockets[pocket_name].history()

    async def get_height(self):
        return await self.client.last_height()

class Pocket:

    def __init__(self, main_key, index, settings, parent):
        self._main_key = main_key
        self._index = index
        self._settings = settings
        self._parent = parent
        self._history = {}
        self._transactions = {}

    @classmethod
    def from_json(cls, values, settings, parent):
        key = bc.HdPrivate.from_string(values["main_key"])
        index = values["index"]
        pocket = cls(key, index, settings, parent)
        pocket._keys = [bc.HdPrivate.from_string(key_str)
                        for key_str in values["keys"]]
        return pocket

    def initialize(self):
        # Generate gap_limit (default is 5) new keys
        self._keys = [
            self._main_key.derive_private(i + bc.hd_first_hardened_key)
            for i in range(self._settings.gap_limit)
        ]

    def serialize(self):
        keys = [key.encoded() for key in self._keys]
        return {
            "main_key": self._main_key.encoded(),
            "index": self._index,
            "keys": keys
        }

    @property
    def addresses(self):
        addresses = []
        version = bc.EcPrivate.mainnet
        if self._parent.testnet:
            version = bc.EcPrivate.testnet
        for key in self._keys:
            secret = key.secret()
            private = bc.EcPrivate.from_secret(secret, version)
            address = bc.PaymentAddress.from_secret(private)
            assert address.is_valid()
            addresses.append(str(address))
        return addresses

    @property
    def _client(self):
        return self._parent.client

    async def scan(self):
        for address in self.addresses:
            await self._process(address)

    async def _process(self, address):
        ec, history = await self._client.history(address)
        if ec:
            print("Couldn't fetch history:", ec, file=sys.stderr)
            return
        self._history[address] = history
        output_tx_hashes = [output[0].hash for output, _ in history]
        for tx_hash in output_tx_hashes:
            ec, tx_data = await self._client.transaction(tx_hash)
            if ec:
                print("Couldn't fetch transaction:", ec, tx_hash.hex(),
                      file=sys.stderr)
                continue
            self._transactions[tx_hash] = tx_data

    def balance(self):
        address_balance = lambda history: \
            sum(output[2] for output, spend in history if spend is None)
        total_balance = lambda history_map: \
            sum(address_balance(history) for history in history_map.values())
        return total_balance(self._history)

    def history(self):
        # Combine all address histories into one
        flatten = lambda l: [item for sublist in l for item in sublist]
        all_history = flatten(self._history.values())
        result = []
        for output, _ in all_history:
            point, height, value = output
            result.append(("1bc", value, height))
        # TODO: add spend
        def get_key(item):
            return item[2]
        result.sort(key=get_key)
        return result

def create_brainwallet_seed():
    entropy = os.urandom(16)
    return bc.create_mnemonic(entropy)

class Wallet:

    def __init__(self, context, settings):
        self._context = context
        self._settings = settings

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

    async def create_account(self, account_name, password, use_testnet):
        print("create_account", account_name, password)
        if account_name in self._account_names:
            return ErrorCode.duplicate, []

        # Create new seed
        wordlist = create_brainwallet_seed()
        print("Wordlist:", wordlist)
        seed = bc.decode_mnemonic(wordlist).data

        account_filename = self.account_filename(account_name)
        # Init current account object
        self._account = Account(account_name, account_filename, password,
                                self._context, self._settings)
        self._account.set_seed(seed, wordlist, use_testnet)
        self._account.save()
        self._account.start()
        self._account_names.append(account_name)

        # Create master pocket
        self._account.create_pocket(self._settings.master_pocket_name)

        return None, []

    async def seed(self):
        if self._account is None:
            return ErrorCode.no_active_account_set, []
        return None, self._account.brainwallet_wordlist()

    async def restore_account(self, account, brainwallet,
                              password, use_testnet):
        print("restore_account", account, brainwallet, password)
        # Create new seed
        wordlist = brainwallet.strip().split(" ")
        if not bc.validate_mnemonic(wordlist):
            return ErrorCode.invalid_brainwallet, []
        seed = bc.decode_mnemonic(wordlist).data

        account_filename = self.account_filename(account_name)
        # Init current account object
        self._account = Account(account_name, account_filename, password,
                                self._context, self._settings)
        self._account.set_seed(seed, worldlist, use_testnet)
        self._account.save()
        self._account.start()
        self._account.spawn_scan()
        self._account_names.append(account_name)

        # Create master pocket
        self._account.create_pocket(self._settings.master_pocket_name)

        return None, []

    async def balance(self, pocket):
        if self._account is None:
            return ErrorCode.no_active_account_set, []
        return self._account.balance(pocket)

    async def history(self, pocket):
        if self._account is None:
            return ErrorCode.no_active_account_set, []
        return self._account.history(pocket)

    async def list_accounts(self):
        account_name = None if self._account is None else self._account.name
        return None, [account_name, self._account_names]

    async def set_account(self, account_name, password):
        if not account_name in self._account_names:
            return ErrorCode.not_found, []
        account_filename = self.account_filename(account_name)
        # Init current account object
        self._account = Account(account_name, account_filename, password,
                                self._context, self._settings)
        if not self._account.load():
            self._account = None
            return ErrorCode.wrong_password, []
        self._account.start()
        self._account.spawn_scan()
        return None, []

    async def delete_account(self, account_name):
        if not account_name in self._account_names:
            return ErrorCode.not_found, []
        if self._account is not None and self._account.name == account_name:
            self._account = None
        self._account_names.remove(account_name)
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
        ec, addresses = self._account.receive(pocket)
        return ec, addresses

    async def get_height(self):
        if self._account is None:
            return ErrorCode.no_active_account_set, []
        ec, height = await self._account.get_height()
        return ec, [height]

    async def get_setting(self, name):
        try:
            value = getattr(self._settings, name)
        except AttributeError:
            return ErrorCode.not_found, []
        return None, [value]

    async def set_setting(self, name, value):
        try:
            setattr(self._settings, name, value)
        except AttributeError:
            return ErrorCode.not_found, []
        self._settings.save()
        return None, []

