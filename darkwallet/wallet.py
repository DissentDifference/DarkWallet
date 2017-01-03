import asyncio
import enum
import json
import os
import random
import sys

import libbitcoin.server
from libbitcoin.server_fake_async import Client
import darkwallet.util
from libbitcoin import bc
from darkwallet import sodium
from darkwallet.stealth import StealthReceiver, StealthSender
from darkwallet.address_validator import AddressValidator

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
    not_enough_funds = 6
    invalid_address = 7

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
        self.current_index = (None, None)

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
    def current_index(self):
        return self.current_height, self.current_hash
    @current_index.setter
    def current_index(self, current_index):
        block_height, block_hash = current_index
        if block_hash is not None:
            block_hash = bc.encode_hash(block_hash)
        self._model["current_index"] = (block_height, block_hash)

    @property
    def current_height(self):
        return self._model["current_index"][0]

    @property
    def current_hash(self):
        block_hash = self._model["current_index"][1]
        if block_hash is None:
            return None
        return bc.hash_literal(block_hash)

    def compare_indexes(self, index):
        block_height, block_hash = self.current_index
        if block_height != index[0]:
            return False
        if block_hash != index[1]:
            return False
        return True

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
            },
            "stealth": {
                "keys": {
                }
            }
        }
        key = self.root_key.derive_private(i + bc.hd_first_hardened_key)
        self.pocket(name).index = i
        self.pocket(name).main_key = key
        self.pocket(name).create_stealth()
        return self.pocket(name)

    def pocket(self, name):
        if name not in self.pocket_names:
            return None
        return PocketModel(self._model["pockets"][name],
                           self.cache.history, self.testnet)

    @property
    def pocket_names(self):
        return list(self._model["pockets"].keys())

    @property
    def pockets(self):
        return [PocketModel(pocket, self.cache.history, self.testnet)
                for pocket in self._model["pockets"].values()]

    def delete_pocket(self, name):
        del self._model["pockets"][name]

    @property
    def cache(self):
        return CacheModel(self._model["cache"])

    def all_unspent_inputs(self):
        return flatten(pocket.unspent_inputs for pocket in self.pockets)

    def find_key(self, addr):
        for pocket in self.pockets:
            key = pocket.key_from_addr(addr)
            if key is not None:
                return key
        return None

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

    def create_stealth(self):
        model = self._model["stealth"]

        first_key = self.main_key.derive_private(0 + bc.hd_first_hardened_key)
        scan_private = first_key.derive_private(0 + bc.hd_first_hardened_key)
        spend_private = first_key.derive_private(1 + bc.hd_first_hardened_key)
        model["scan_private"] = scan_private.secret().data.hex()
        model["spend_private"] = [
            spend_private.secret().data.hex()
        ]

    def _get_secret(self, i):
        return bc.HdPrivate.from_string(self._model["keys"][i]).secret()

    def _get_stealth_secret(self, address):
        address = address.encoded()
        if address not in self.addrs_from_stealth:
            return None
        key_data = self._model["stealth"]["keys"][address]
        return bc.EcSecret.from_string(key_data)

    def key_from_addr(self, address):
        i = self.addr_index(address)
        if i is not None:
            return self._get_secret(i)
        stealth_key = self._get_stealth_secret(address)
        if stealth_key is not None:
            return stealth_key
        return None

    @property
    def addrs(self):
        return self.addrs_nonstealth + self.addrs_from_stealth

    @property
    def addrs_nonstealth(self):
        return list(self._model["addrs"].values())

    @property
    def addrs_from_stealth(self):
        return list(self._model["stealth"]["keys"].keys())

    def addr_index(self, addr):
        if isinstance(addr, bc.PaymentAddress):
            addr = addr.encoded()
        addrs_map = self._model["addrs"].items()
        results = [item[0] for item in addrs_map if item[1] == addr]
        if not results:
            return None
        assert len(results) == 1
        index = results[0]
        return index

    @property
    def stealth_scan_private(self):
        return bc.EcSecret.from_bytes(bytes.fromhex(
            self._model["stealth"]["scan_private"]))

    @property
    def stealth_spend_privates(self):
        unhex = lambda spend_hex: bytes.fromhex(spend_hex)
        convert = lambda spend_data: bc.EcSecret.from_bytes(unhex(spend_data))
        spend_keys = self._model["stealth"]["spend_private"]
        return [convert(spend_data) for spend_data in spend_keys]

    @property
    def stealth_receiver(self):
        assert self.stealth_spend_privates
        spend_private = self.stealth_spend_privates[0]
        return StealthReceiver(self.stealth_scan_private, spend_private,
                               self.address_version())

    def address_version(self):
        if self._testnet:
            return bc.PaymentAddress.testnet_p2kh
        return bc.PaymentAddress.mainnet_p2kh

    @property
    def stealth_address(self):
        return self.stealth_receiver.generate_stealth_address()

    def add_stealth_key(self, address, key):
        self._model["stealth"]["keys"][address.encoded()] = key.data.hex()

    def get_stealth_key(self, address):
        if isinstance(address, bc.PaymentAddress):
            address = address.encoded()
        key_data = bytes.fromhex(self._model["stealth"]["keys"][address])
        key = bc.EcSecret.from_bytes(key_data)
        assert key.data.hex() == self._model["stealth"]["keys"][address]
        return key

    def __len__(self):
        return len(self._model["keys"])

    @property
    def history(self):
        addrs = [addr for addr in self.addrs if addr in self._history_model]
        result = {}
        for addr in addrs:
            result[addr] = self._history_model[addr]
        return result

    @property
    def flat_history(self):
        return flatten(self.history.values())

    def balance(self):
        return sum(row.value for row in self.flat_history)

    @property
    def unspent_inputs(self):
        # [(point, value), ...]
        unspent = [row for row in self.flat_history
                   if row.is_unspent_output()]
        unspent = [((row.hash, row.index), row.value) for row in unspent]
        return unspent

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

    def clear(self):
        self._model.clear()

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
        return [row.hash for row in self.all()]

class HistoryRowModel:

    def __init__(self, model):
        self._model = model

    @property
    def model(self):
        return self._model

    @property
    def object(self):
        if self.is_output():
            return self._model["output"]
        elif self.is_spend():
            return self._model["spend"]

    def is_output(self):
        return self._model["type"] == "output"

    def is_spend(self):
        return self._model["type"] == "spend"

    def is_spent_output(self):
        return self.is_output() and self.spend is not None

    def is_unspent_output(self):
        return self.is_output() and not self.is_spent_output()

    @property
    def hash(self):
        return bc.hash_literal(self.object["hash"])

    @property
    def index(self):
        return self.object["index"]

    @property
    def height(self):
        return self.object["height"]

    @property
    def value(self):
        return self._model["value"]

    @property
    def spend(self):
        return self._model["spend"]

class TransactionModel:

    def __init__(self, model):
        self._model = model

    def __getitem__(self, tx_hash):
        if isinstance(tx_hash, bc.HashDigest):
            tx_hash = bc.encode_hash(tx_hash)
        tx_data = bytes.fromhex(self._model[tx_hash])
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
        self._context = context
        self._settings = settings

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
        self.save()
        self._stopped = True

    def spawn_scan(self):
        loop = asyncio.get_event_loop()
        loop.create_task(self._check_updates())

    async def _check_updates(self):
        self.current_height = None
        self.current_hash = None
        while not self._stopped:
            await self._query_blockchain_reorg()
            await asyncio.sleep(5)

    async def _query_blockchain_reorg(self):
        head = await self._query_blockchain_head()
        if head is None:
            return
        height, header = head
        index = height, header.hash()
        if self._model.compare_indexes(index):
            # Nothing changed.
            return
        if header.previous_block_hash == self._model.current_hash:
            print("New block added.")
            from_height = height
        else:
            print("Blockchain reorganization event.")
            from_height = 0
            self._clear_history()
        await self._update(index, from_height)
        self._finish_reorg(index)

    async def _query_blockchain_head(self):
        ec, height = await self.client.last_height()
        if ec:
            print("Error: querying last_height:", ec, file=sys.stderr)
            return None
        ec, header = await self.client.block_header(height)
        if ec:
            print("Error: querying header:", ec, file=sys.stderr)
            return None
        header = bc.Header.from_data(header)
        return height, header

    def _clear_history(self):
        self._model.cache.history.clear()

    async def _update(self, index, from_height):
        await self._query_stealth(from_height)
        await self._sync_history(from_height)
        #print("Scanned.")
        await self._fill_cache()
        #print("Cache filled.")
        #print(json.dumps(self._model._model, indent=2))
        await self._generate_keys()
        print("Updated:", json.dumps(self._model._model, indent=2))

    def _finish_reorg(self, index):
        print("Updating current_index to:", index)
        self._model.current_index = index

    async def _sync_history(self, from_height):
        addrs = []
        for pocket_name in self._model.pocket_names:
            pocket = self._model.pocket(pocket_name)
            addrs.extend(pocket.addrs)

        for addr in addrs:
            await self._scan(addr, from_height)

    async def _scan(self, addr, from_height):
        #print("Scanning:", addr)
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
            if addr not in self._model.cache.history:
                continue
            if self._model.cache.history[addr]:
                i = pocket.addr_index(addr)
                if i is None:
                    continue
                max_i = max(i, max_i)
        desired_len = max_i + 1 + self._settings.gap_limit
        remaining = desired_len - len(pocket)
        [pocket.add_key() for i in range(remaining)]

    async def _query_stealth(self, from_height):
        genesis_height = 0
        if self._model.testnet:
            genesis_height = 1063370
        from_height = max(genesis_height, from_height)
        # We haven't implemented prefixes yet.
        prefix = libbitcoin.server.Binary(0, b"")
        print("Starting stealth query. [from_height=%s]" % from_height)
        ec, rows = await self.client.stealth(prefix, from_height)
        print("Stealth query done.")
        if ec:
            print("Error: query stealth:", ec, file=sys.stderr)
            return
        for ephemkey, address_hash, tx_hash in rows:
            ephemeral_public = bytes([2]) + ephemkey[::-1]
            ephemeral_public = bc.EcCompressed.from_bytes(ephemeral_public)

            version = bc.PaymentAddress.mainnet_p2kh
            if self._model.testnet:
                version = bc.PaymentAddress.testnet_p2kh

            address = bc.PaymentAddress.from_hash(address_hash[::-1],
                                                  version)
            
            tx_hash = bc.HashDigest.from_bytes(tx_hash[::-1])

            await self._scan_all_pockets_for_stealth(ephemeral_public,
                                                     address, tx_hash)

    async def _scan_all_pockets_for_stealth(self, ephemeral_public,
                                            original_address, tx_hash):
        for pocket in self._model.pockets:
            await self._scan_pocket_for_stealth(pocket, ephemeral_public,
                                                original_address, tx_hash)

    async def _scan_pocket_for_stealth(self, pocket, ephemeral_public,
                                       original_address, tx_hash):
        receiver = pocket.stealth_receiver
        derived_address = receiver.derive_address(ephemeral_public)
        if derived_address is None or original_address != derived_address:
            return
        assert original_address == derived_address
        print("Found match:", derived_address)
        
        private_key = receiver.derive_private(ephemeral_public)
        pocket.add_stealth_key(original_address, private_key)

    def list_pockets(self):
        return self._model.pocket_names

    def create_pocket(self, pocket_name):
        pocket_model = self._model.add_pocket(pocket_name)

        if pocket_model is None:
            return ErrorCode.duplicate

        return None

    def delete_pocket(self, pocket_name):
        if pocket_name not in self._model.pocket_names:
            return ErrorCode.not_found

        self._model.delete_pocket(pocket_name)
        return None

    @property
    def all_unused_addrs(self):
        unused_addrs = [self.unused_addrs(pocket) for pocket
                        in self._model.pockets]
        return flatten(unused_addrs)

    def _filter_unused(self, addrs):
        return [address for address in addrs if not self.is_used(address)]

    def unused_addrs(self, pocket):
        return self._filter_unused(pocket.addrs_nonstealth)

    def is_used(self, addr):
        if addr not in self._model.cache.history.addrs:
            return False
        return True if self._model.cache.history[addr] else False

    def receive(self, pocket_name=None):
        if pocket_name is None:
            return None, [self.all_unused_addrs]

        pocket = self._model.pocket(pocket_name)
        if pocket is None:
            return ErrorCode.not_found, []

        return None, [self.unused_addrs(pocket)]

    def stealth(self, pocket_name=None):
        if pocket_name is None:
            pocket_name = random.choice(self._model.pocket_names)

        pocket = self._model.pocket(pocket_name)
        if pocket is None:
            return ErrorCode.not_found, None

        return None, str(pocket.stealth_address)

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
        return flatten(self._query_history(pocket_name)
                       for pocket_name in self._model.pocket_names)

    def history(self, pocket_name=None):
        if pocket_name is None:
            # Most recent history from all pockets
            return None, self.combined_history

        history = self._query_history(pocket_name)
        if history is None:
            return ErrorCode.not_found, []

        return None, history

    def _query_history(self, pocket_name):
        pocket = self._model.pocket(pocket_name)
        if pocket is None:
            return None

        history = flatten(
            [
                row.model for row in history
            ] for addr, history in pocket.history.items() if history
        )
        return history

    async def get_height(self):
        return await self.client.last_height()

    def _is_correct_address(self, address):
        validator = AddressValidator(address)
        if not validator.is_valid():
            return False

        if validator.is_stealth():
            return True

        if self._model.testnet:
            if not validator.is_testnet():
                return False
        else:
            if not validator.is_mainnet():
                return False

        return validator.is_p2kh()

    async def send(self, dests, from_pocket, fee):
        for address, value in dests:
            if not self._is_correct_address(address):
                return ErrorCode.invalid_address, None
        # Input:
        #   [(point, value), ...]
        #   minimum_value
        # Returns:
        #   [point, ...], change

        # If no pocket, select all unspent
        unspent = self._unspent_inputs(from_pocket)

        # Amount that we are sending + the fee we will pay.
        minimum_value = sum(value for addr, value in dests) + fee

        out = self._select_outputs(unspent, minimum_value)
        if out is None:
            return ErrorCode.not_enough_funds, None

        tx = await self._build_transaction(out, dests, from_pocket)

        # signature, input
        await self._sign(tx)

        print("Broadcasting:", tx.to_data().hex())
        ec = await self.client.broadcast(tx.to_data())
        return ec, bc.encode_hash(tx.hash())

    def _unspent_inputs(self, from_pocket):
        pocket = self._model.pocket(from_pocket)
        if pocket is None:
            return self._model.all_unspent_inputs()
        return pocket.unspent_inputs

    def _select_outputs(self, unspent, minimum_value):
        out = bc.select_outputs(unspent, minimum_value)
        if not out.points:
            return None
        return out

    async def _build_transaction(self, out, dests, change_pocket=None):
        tx = bc.Transaction()
        tx.set_version(1)
        tx.set_locktime(0)

        inputs = [self._create_input(point) for point in out.points]
        tx.set_inputs(inputs)

        outputs = [self._create_outputs(addr, value) for addr, value in dests]
        if out.change:
            outputs += [self._create_change_output(change_pocket, out.change)]
        random.shuffle(outputs)
        outputs = flatten(outputs)
        tx.set_outputs(outputs)

        return tx

    def _create_input(self, point):
        input = bc.Input()
        input.set_sequence(bc.max_uint32)
        input.set_previous_output(point)

        # Set the input script.
        return input

    def _create_outputs(self, addr, value):
        validator = AddressValidator(addr)
        if validator.is_p2kh():
            return [self._create_p2kh_output(addr, value)]
        elif validator.is_stealth():
            return self._create_stealth_outputs(addr, value)
        assert False

    def _create_p2kh_output(self, addr, value):
        output = bc.Output()
        output.set_value(value)

        # Set the output script.
        address = bc.PaymentAddress.from_string(addr)
        script = bc.Script.from_ops(
            bc.Script.to_pay_key_hash_pattern(address.hash()))
        output.set_script(script)
        return output

    def _create_stealth_outputs(self, stealth_addr, value):
        if self._model.testnet:
            sender = StealthSender(bc.PaymentAddress.testnet_p2kh)
        else:
            sender = StealthSender(bc.PaymentAddress.mainnet_p2kh)

        meta_script, send_address = sender.send_to_stealth_address(stealth_addr)

        meta_output = bc.Output()
        meta_output.set_value(0)
        meta_output.set_script(meta_script)

        pay_output = self._create_p2kh_output(send_address.encoded(), value)

        return [meta_output, pay_output]

    def _create_change_output(self, change_pocket, change_value):
        # Choose random pocket if there's no change pocket specified.
        if change_pocket is None:
            change_pocket = random.choice(self._model.pocket_names)

        pocket = self._model.pocket(change_pocket)

        output = bc.Output()
        output.set_value(change_value)

        unused_addrs = self.unused_addrs(pocket)
        # Send change to random unspent address in pocket
        address = bc.PaymentAddress.from_string(
            random.choice(unused_addrs))
        script = bc.Script.from_ops(
            bc.Script.to_pay_key_hash_pattern(address.hash()))
        output.set_script(script)

        return [output]

    async def _sign(self, tx):
        inputs = tx.inputs()

        for input_index, input in enumerate(inputs):
            signature = await self._sign_input(tx, input, input_index)

            public_key = self._get_public_key(input)

            script = bc.Script.from_ops([
                bc.Operation.from_data(signature),
                bc.Operation.from_data(public_key)
            ])

            assert bc.Script.is_sign_key_hash_pattern(script.operations())

            input.set_script(script)

        tx.set_inputs(inputs)

    async def _sign_input(self, tx, input, input_index):
        prevout_script = self._get_prevout_script(input)

        # Secret.
        secret = self._get_secret(prevout_script)

        return bc.Script.create_endorsement(
            secret, prevout_script, tx, input_index, bc.SighashAlgorithm.all)

    def _get_prevout_script(self, input):
        # Find tx and output.
        previous_output_point = input.previous_output()
        tx_hash, previous_index = (previous_output_point.hash(),
                                   previous_output_point.index())
        previous_tx = self._model.cache.transactions[tx_hash]
        # Address from output.
        previous_output = previous_tx.outputs()[previous_index]
        prevout_script = previous_output.script()
        return prevout_script

    def _get_secret(self, prevout_script):
        # Get key for that address.
        address = self._extract(prevout_script)
        return self._model.find_key(address)

    def _get_public_key(self, input):
        prevout_script = self._get_prevout_script(input)
        secret = self._get_secret(prevout_script)
        return secret.to_public().data

    def _extract(self, prevout_script):
        p2kh = bc.PaymentAddress.mainnet_p2kh
        p2sh = bc.PaymentAddress.mainnet_p2sh
        if self._model.testnet:
            p2kh = bc.PaymentAddress.testnet_p2kh
            p2sh = bc.PaymentAddress.testnet_p2sh
        return bc.PaymentAddress.extract(prevout_script, p2kh, p2sh)

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

    async def restore_account(self, account_name, wordlist,
                              password, use_testnet):
        print("restore_account", account_name, wordlist, password)
        # Create new seed
        if not bc.validate_mnemonic(wordlist):
            return ErrorCode.invalid_brainwallet, []
        seed = bc.decode_mnemonic(wordlist).data

        account_filename = self.account_filename(account_name)
        # Init current account object
        self._account = Account(account_name, account_filename, password,
                                self._context, self._settings)
        self._account.set_seed(seed, wordlist, use_testnet)
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
        ec = self._account.create_pocket(pocket)
        self._settings.save()
        return ec, []

    async def delete_pocket(self, pocket):
        if self._account is None:
            return ErrorCode.no_active_account_set, []
        ec = self._account.delete_pocket(pocket)
        self._settings.save()
        return ec, []

    async def send(self, dests, from_pocket, fee):
        if self._account is None:
            return ErrorCode.no_active_account_set, []
        dests = [(addr, int(amount)) for addr, amount in dests]
        ec, tx_hash = await self._account.send(dests, from_pocket, fee)
        return ec, [tx_hash]

    async def receive(self, pocket):
        if self._account is None:
            return ErrorCode.no_active_account_set, []
        ec, addresses = self._account.receive(pocket)
        return ec, addresses

    async def stealth(self, pocket):
        if self._account is None:
            return ErrorCode.no_active_account_set, []
        ec, stealth_address = self._account.stealth(pocket)
        return ec, [stealth_address]

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

