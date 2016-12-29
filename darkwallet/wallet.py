import asyncio
import enum
import json
import os
import sys

import libbitcoin.server
from libbitcoin.server_fake_async import Client
import darkwallet.util
from libbitcoin import bc
from darkwallet import sodium

flatten = lambda l: [item for sublist in l for item in sublist]

def write_json(filename, json_object):
    open(filename, "w").write(json.dumps(json_object))

def read_json(filename):
    return json.loads(open(filename).read())

def hd_private_key_address(key, version):
    secret = key.secret()
    private = bc.EcPrivate.from_secret(secret, version)
    address = bc.PaymentAddress.from_secret(private)
    assert address.is_valid()
    return str(address)

class ErrorCode(enum.Enum):

    wrong_password = 1
    invalid_brainwallet = 2
    no_active_account_set = 3
    duplicate = 4
    not_found = 5

class AccountModel:

    def __init__(self, filename):
        self._filename = filename
        self._model = {
            "pockets": {
            },
            "cache": {
                "history": {
                },
                "transactions": {
                }
            }
        }

    def load(self, password):
        encrypted_wallet_info = read_json(self._filename)
        salt, nonce, ciphertext = (
            bytes.fromhex(encrypted_wallet_info["salt"]),
            bytes.fromhex(encrypted_wallet_info["nonce"]),
            bytes.fromhex(encrypted_wallet_info["encrypted_wallet"])
        )
        message = sodium.decrypt(salt, nonce, ciphertext, password)
        if message is None:
            return False
        message = str(message, "ascii")
        self._model = json.loads(message)
        print("Loading:", json.dumps(self._model, indent=2))
        return True

    def save(self, password):
        print(self._model)
        print("Saving:", json.dumps(self._model, indent=2))
        message = bytes(json.dumps(self._model), "utf-8")
        salt, nonce, ciphertext = sodium.encrypt(message, password)
        encrypted_wallet_info = {
            "encrypted_wallet": ciphertext.hex(),
            "salt": salt.hex(),
            "nonce": nonce.hex()
        }
        write_json(self._filename, encrypted_wallet_info)

    @property
    def seed(self):
        return bytes.fromhex(self._model["seed"])
    @seed.setter
    def seed(self, seed):
        self._model["seed"] = seed.hex()

    @property
    def wordlist(self):
        return self._model["wordlist"]
    @wordlist.setter
    def wordlist(self, wordlist):
        self._model["wordlist"] = wordlist

    @property
    def testnet(self):
        return self._model["testnet"]
    @testnet.setter
    def testnet(self, testnet):
        self._model["testnet"] = testnet

    @property
    def root_key(self):
        prefixes = bc.HdPrivate.mainnet
        if self.testnet:
            prefixes = bc.HdPrivate.testnet
        return bc.HdPrivate.from_seed(self.seed, prefixes)

    def add_pocket(self, name):
        if name in self._model["pockets"]:
            return None
        i = len(self._model["pockets"])
        self._model["pockets"][name] = {
            "keys": [
            ],
            "addrs": {
            }
        }
        key = self.root_key.derive_private(i + bc.hd_first_hardened_key)
        self.pocket(name).index = i
        self.pocket(name).main_key = key
        return self.pocket(name)

    def pocket(self, name):
        return PocketModel(self._model["pockets"][name],
                           self.cache.history, self.testnet)

    @property
    def pocket_names(self):
        return self._model["pockets"].keys()

    @property
    def pockets(self):
        return [PocketModel(pocket, self.cache.history, self.testnet)
                for pocket in self._model["pockets"].values()]

    @property
    def cache(self):
        return CacheModel(self._model["cache"])

class PocketModel:

    def __init__(self, model, history_model, testnet):
        self._model = model
        self._history_model = history_model
        self._testnet = testnet

        # Json converts dict keys to strings. Convert them back.
        self._model["addrs"] = {int(key): value for key, value
                                in self._model["addrs"].items()}

    @property
    def main_key(self):
        return bc.HdPrivate.from_string(self._model["main_key"])
    @main_key.setter
    def main_key(self, main_key):
        self._model["main_key"] = main_key.encoded()

    @property
    def index(self):
        return self._model["index"]
    @index.setter
    def index(self, index):
        self._model["index"] = index

    def add_key(self):
        i = len(self._model["keys"])
        key = self.main_key.derive_private(i + bc.hd_first_hardened_key)
        key_str = key.encoded()
        self._model["keys"].append(key_str)

        version = bc.EcPrivate.mainnet
        if self._testnet:
            version = bc.EcPrivate.testnet
        addr = hd_private_key_address(key, version)
        self._model["addrs"][i] = addr

    def key(self, i):
        return bc.HdPrivate.from_string(self._model["keys"][i])

    def key_from_addr(self, addr):
        index = self.index(addr)
        return self.key(index)

    @property
    def addrs(self):
        return self._model["addrs"].values()

    def index(self, addr):
        addrs_map = self._model["addrs"].items()
        results = [item[0] for item in addrs_map if item[1] == addr]
        assert len(results) == 1
        index = results[0]
        return index

    def __len__(self):
        return len(self._model["keys"])

    @property
    def history(self):
        addrs = [addr for addr in self.addrs if addr in self._history_model]
        result = {}
        for addr in addrs:
            result[addr] = self._history_model[addr]
        return result

    def balance(self):
        rows = flatten(self.history.values())
        return sum(row.value for row in rows)

class CacheModel:

    def __init__(self, model):
        self._model = model

    @property
    def history(self):
        return HistoryModel(self._model["history"])

    @property
    def transactions(self):
        return TransactionModel(self._model["transactions"])

class HistoryModel:

    def __init__(self, model):
        self._model = model

    @property
    def addrs(self):
        return self._model.keys()

    def __getitem__(self, addr):
        return [HistoryRowModel(row) for row in self._model[addr]]

    def __setitem__(self, addr, history):
        history_model = []
        for output, spend in history:
            if spend is None:
                spend = None
            else:
                spend = {
                    "hash": spend[0].hash.hex(),
                    "index": spend[0].index,
                    "height": spend[1]
                }
                history_model.append({
                    "type": "spend",
                    "addr": addr,
                    "spend": spend,
                    "value": -output[2],
                })
            history_model.append({
                "type": "output",
                "addr": addr,
                "output": {
                    "hash": output[0].hash.hex(),
                    "index": output[0].index,
                    "height": output[1],
                },
                "value": output[2],
                "spend": spend
            })
        self._model[addr] = history_model

    def __contains__(self, addr):
        return addr in self._model

    def values(self):
        return [[HistoryRowModel(row) for row in history]
                for history in self._model.values()]

    def all(self, from_height=0):
        all_rows = flatten(self.values())
        all_rows = [row for row in all_rows if row.height >= from_height]
        return all_rows

    @property
    def transaction_hashes(self):
        return [row.transaction_hash for row in self.all()]

class HistoryRowModel:

    def __init__(self, model):
        self._model = model

    @property
    def object(self):
        if self._model["type"] == "output":
            return self._model["output"]
        elif self._model["type"] == "spend":
            return self._model["spend"]

    @property
    def transaction_hash(self):
        return bc.hash_literal(self.object["hash"])

    @property
    def height(self):
        return self.object["height"]

    @property
    def value(self):
        return self._model["value"]

class TransactionModel:

    def __init__(self, model):
        self._model = model

    def __getitem__(self, tx_hash):
        if isinstance(tx_hash, bc.HashDigest):
            tx_hash = str(tx_hash)
        tx_data = self._model[tx_hash]
        tx = bc.Transaction.from_data(tx_data)
        assert tx is not None
        assert tx.is_valid()
        return tx

    def __setitem__(self, tx_hash, tx):
        self._model[bc.encode_hash(tx_hash)] = tx.hex()

    def __contains__(self, tx_hash):
        return bc.encode_hash(tx_hash) in self._model

class Account:

    def __init__(self, name, filename, password, context, settings):
        self.name = name
        self._pockets = {}
        self._context = context
        self._settings = settings

        self._filename = filename
        self._password = bytes(password, "utf-8")

        self._model = AccountModel(filename)
        self.client = None

        self._stopped = False

    def brainwallet_wordlist(self):
        return self._model.wordlist

    def set_seed(self, seed, wordlist, testnet):
        self._model.seed = seed
        self._model.wordlist = wordlist
        self._model.testnet = testnet

    def save(self):
        self._model.save(self._password)

    def load(self):
        return self._model.load(self._password)

    def start(self):
        client_settings = libbitcoin.server.ClientSettings()
        client_settings.query_expire_time = self._settings.query_expire_time
        client_settings.socks5 = self._settings.socks5
        url = self._settings.url
        if self._model.testnet:
            url = self._settings.testnet_url
        self.client = Client(self._context, url, client_settings)

    def stop(self):
        self._stopped = True

    def spawn_scan(self):
        loop = asyncio.get_event_loop()
        loop.create_task(self._check_updates())

    async def _check_updates(self):
        while not self._stopped:
            await self._sync_history()
            print("Scanned.")
            await self._fill_cache()
            print("Cache filled.")
            print("--------------")
            print(json.dumps(self._model._model, indent=2))
            await self._generate_keys()
            await asyncio.sleep(5)

    async def _sync_history(self):
        addrs = []
        for pocket_name in self._model.pocket_names:
            pocket = self._model.pocket(pocket_name)
            addrs.extend(pocket.addrs)

        for addr in addrs:
            await self._scan(addr)

    async def _scan(self, addr):
        print("Scanning:", addr)
        ec, history = await self.client.history(addr)
        if ec:
            print("Couldn't fetch history:", ec, file=sys.stderr)
            return

        self._model.cache.history[addr] = history

    async def _fill_cache(self):
        for tx_hash in self._model.cache.history.transaction_hashes:
            if not tx_hash in self._model.cache.transactions:
                await self._grab_tx(tx_hash)

    async def _grab_tx(self, tx_hash):
        print(bc.encode_hash(tx_hash))
        ec, tx = await self.client.transaction(tx_hash.data)
        if ec:
            print("Couldn't fetch transaction:", ec, file=sys.stderr)
            return
        print("Got tx:", tx_hash)
        self._model.cache.transactions[tx_hash] = tx

    async def _generate_keys(self):
        for pocket in self._model.pockets:
            self._generate_pocket_keys(pocket)

    def _generate_pocket_keys(self, pocket):
        max_i = -1
        for addr in pocket.addrs:
            if self._model.cache.history[addr]:
                i = pocket.index(addr)
                max_i = max(i, max_i)
        desired_len = max_i + 1 + self._settings.gap_limit
        remaining = desired_len - len(pocket)
        [pocket.add_key() for i in range(remaining)]

    def list_pockets(self):
        return self._model.pocket_names

    def create_pocket(self, pocket_name):
        pocket_model = self._model.add_pocket(pocket_name)

        if pocket_model is None:
            return ErrorCode.duplicate

        return None

    def delete_pocket(self, pocket_name):
        # TODO
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
        # TODO
        if pocket_name is not None and pocket_name not in self._pockets:
            return ErrorCode.not_found, []
        if pocket_name is None:
            return None, [self.all_addresses]
        return None, [self._pockets[pocket_name].addresses]

    @property
    def total_balance(self):
        return sum(pocket.balance() for pocket in self._model.pockets)

    def balance(self, pocket_name=None):
        if pocket_name is None:
            return None, [self.total_balance]

        pocket = self._model.pocket(pocket_name)
        if pocket is None:
            return ErrorCode.not_found, []

        return None, [pocket.balance()]

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
        # TODO
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
        self._transactions_cache = {}
        self._keys = []
        self._last_used_key_index = -1

    @classmethod
    def from_json(cls, values, settings, parent):
        key = bc.HdPrivate.from_string(values["main_key"])
        index = values["index"]
        pocket = cls(key, index, settings, parent)
        pocket._keys = [bc.HdPrivate.from_string(key_str)
                        for key_str in values["keys"]]
        return pocket

    def generate_keys(self):
        assert self.total_needed_keys >= len(self._keys)
        extra_needed_keys = self.total_needed_keys - len(self._keys)
        print("Generating %s extra keys (current length is %s)." % (
              extra_needed_keys, len(self._keys)))
        # Always ensure gap_limit (default 5) extra keys exist.
        self._keys.extend([
            self._main_key.derive_private(i + bc.hd_first_hardened_key)
            for i in range(extra_needed_keys)
        ])

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
        return [hd_private_key_address(key, version) for key in self._keys]

    @property
    def _client(self):
        return self._parent.client

    @property
    def total_needed_keys(self):
        return self._last_used_key_index + 1 + self._settings.gap_limit

    async def scan(self):
        end_scanned_key_index = 0
        while end_scanned_key_index < len(self._keys):
            remain_addrs = self.addresses[end_scanned_key_index:]
            for index, address in enumerate(remain_addrs):
                await self._process(index, address)
            end_scanned_key_index = len(self._keys)
            self.generate_keys()
        self._parent.save()

    async def _process(self, index, address):
        ec, history = await self._client.history(address)
        if ec:
            print("Couldn't fetch history:", ec, file=sys.stderr)
            return
        if history and index > self._last_used_key_index:
            self._last_used_key_index = index
        self._history[address] = history
        output_tx_hashes = [output[0].hash for output, _ in history]
        for tx_hash in output_tx_hashes:
            ec, tx_data = await self._client.transaction(tx_hash)
            if ec:
                print("Couldn't fetch transaction:", ec, tx_hash.hex(),
                      file=sys.stderr)
                continue
            self._transactions_cache[tx_hash] = tx_data

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

        #self._context.spawn(self._poller)
        self._stopped = False
        #self._context.register(self)

    async def _poller(self):
        while self._stopped:
            asyncio.sleep(20)
            if self._account is None:
                self._account.spawn_scan()

    async def stop(self):
        self._account.stop()
        self._stopped = True

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
        self._account.start()
        self._account.spawn_scan()
        self._account_names.append(account_name)

        # Create master pocket
        self._account.create_pocket(self._settings.master_pocket_name)

        self._account.save()

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

    async def stop(self):
        if self._account is not None:
            self._account.stop()
        self._context.stop()

