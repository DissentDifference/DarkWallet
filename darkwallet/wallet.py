import asyncio
import enum
import json
import os
import random
import sys
from decimal import Decimal

import libbitcoin.server
from libbitcoin.server_fake_async import Client as FakeAsyncClient
from libbitcoin.server import Client
import darkwallet.util
from libbitcoin import bc
from darkwallet import sodium
from darkwallet.stealth import StealthReceiver, StealthSender
from darkwallet.address_validator import AddressValidator

import darkwallet.db as db

flatten = lambda l: [item for sublist in l for item in sublist]

def write_json(filename, json_object):
    open(filename, "w").write(json.dumps(json_object))

def read_json(filename):
    return json.loads(open(filename).read())

def hd_private_key_to_address(key, is_testnet):
    version = bc.EcPrivate.mainnet
    if is_testnet:
        version = bc.EcPrivate.testnet
    secret = key.secret()
    private = bc.EcPrivate.from_secret(secret, version)
    address = bc.PaymentAddress.from_secret(private)
    assert address.is_valid()
    return str(address)

def decimal_to_satoshi(value):
    return int(value * (10**bc.btc_decimal_places))

class ErrorCode(enum.Enum):
    wrong_password = 1
    invalid_brainwallet = 2
    no_active_account_set = 3
    duplicate = 4
    not_found = 5
    not_enough_funds = 6
    invalid_address = 7
    short_password = 8
    updating_history = 9

class AccountModel:

    def __init__(self, filename):
        self._filename = filename
        self._model = None

    def create(self, wordlist, is_testnet):
        try:
            db.create_tables()
        except db.ImproperlyConfigured:
            return ErrorCode.short_password
        self._model = db.Account.create(
            wordlist=wordlist, is_testnet=is_testnet)
        return None

    def load(self):
        try:
            self._model = db.Account.get()
        except (db.ImproperlyConfigured, db.DatabaseError):
            return False
        return True

    @property
    def current_index(self):
        return self.current_height, self.current_hash
    @current_index.setter
    def current_index(self, current_index):
        block_height, block_hash = current_index
        self._model.current_height = block_height
        self._model.current_hash = block_hash
        self._model.save()

    @property
    def current_height(self):
        return self._model.current_height

    @property
    def current_hash(self):
        return self._model.current_hash

    def compare_indexes(self, index):
        height, hash_ = index
        if height != self.current_height:
            return False
        if hash_ != self.current_hash:
            return False
        return True

    @property
    def seed(self):
        wordlist = self._model.wordlist
        return bc.decode_mnemonic(wordlist).data

    @property
    def wordlist(self):
        return self._model.wordlist

    @property
    def is_testnet(self):
        return self._model.is_testnet

    @property
    def root_key(self):
        prefixes = bc.HdPrivate.mainnet
        if self.is_testnet:
            prefixes = bc.HdPrivate.testnet
        return bc.HdPrivate.from_seed(self.seed, prefixes)

    def add_pocket(self, name):
        if name in self.pocket_names:
            return None

        index = len(self.pocket_names)
        key = self.root_key.derive_private(index + bc.hd_first_hardened_key)

        return PocketModel.create(self._model, name, index, key)

    def pocket(self, name):
        if name not in self.pocket_names:
            return None
        model = db.Pocket.get(db.Pocket.name == name)
        return PocketModel(model)

    @property
    def pocket_names(self):
        return [pocket.name for pocket in self._model.pockets]

    @property
    def pockets(self):
        return [PocketModel(model) for model in self._model.pockets]

    def delete_pocket(self, name):
        del self._model["pockets"][name]

    @property
    def cache(self):
        return CacheModel(self._model)

    def all_unspent_inputs(self):
        rows = db.History.select().where(db.History.spend == None,
                                         db.History.is_output == True,
                                         db.History.account == self._model)
        return [HistoryRowModel(row).to_input() for row in rows]

    def find_key(self, address):
        for pocket in self.pockets:
            key = pocket.key_from_address(address)
            if key is not None:
                return key
        return None

    def payment_address_version(self):
        return self._model.payment_address_version()

    def save_pending_transaction(self, dests, tx, pocket):
        pending_tx = db.SentPayments.create(
            tx_hash=tx.hash(),
            tx=tx,
            account=self._model,
            pocket=pocket.model
        )

        for address, value in dests:
            value = Decimal(
                bc.encode_base10(value, bc.btc_decimal_places))
            db.SentPaymentDestinations.create(
                parent=pending_tx,
                address=address,
                value=value
            )

    def mark_sent_transaction_confirmed(self, tx_hash):
        try:
            sent_model = db.SentPayments.get(
                db.SentPayments.tx_hash == tx_hash)
        except db.DoesNotExist:
            return
        print("%s is confirmed." % bc.encode_hash(tx_hash))
        sent_model.is_confirmed = True
        sent_model.save()

    def all_pending_payments(self):
        pending = db.SentPayments.select().where(
            db.SentPayments.is_confirmed == False)
        return [PendingPaymentModel(payment) for payment in pending]

class PocketModel:

    def __init__(self, model):
        self._model = model

    @property
    def is_testnet(self):
        return self._model.is_testnet

    @classmethod
    def create(cls, account_model, name, index, key):
        version = account_model.payment_address_version()
        scan_key, spend_key = PocketModel._derive_stealth_keys(key)
        stealth_addr = PocketModel._derive_stealth_address(
            scan_key, spend_key, version)

        pocket_model = db.Pocket.create(
            account=account_model,
            name=name,
            index_=index,
            main_key=key,
            stealth_address=stealth_addr,
            stealth_scan_key=scan_key,
            stealth_spend_key=spend_key
        )
        return cls(pocket_model)

    @staticmethod
    def _derive_stealth_keys(key):
        first_key = key.derive_private(0 + bc.hd_first_hardened_key)
        scan_private = first_key.derive_private(0 + bc.hd_first_hardened_key)
        spend_private = first_key.derive_private(1 + bc.hd_first_hardened_key)
        return scan_private.secret(), spend_private.secret()

    @staticmethod
    def _derive_stealth_address(scan_key, spend_key, version):
        receiver = StealthReceiver(scan_key, spend_key, version)
        return receiver.generate_stealth_address()

    @property
    def main_key(self):
        return self._model.main_key

    @property
    def index(self):
        return self._model.index_

    def add_key(self):
        index = self.number_normal_keys()
        key = self.main_key.derive_private(index + bc.hd_first_hardened_key)
        address = hd_private_key_to_address(key, self.is_testnet)

        db.PocketKeys.create(
            pocket=self._model,
            index_=index,
            address=address,
            key=key
        )

    def _get_secret(self, address):
        try:
            key_model = db.PocketKeys.get(db.PocketKeys.address == address,
                                          db.PocketKeys.pocket == self._model)
        except db.DoesNotExist:
            return None
        return key_model.secret

    def _get_stealth_secret(self, address):
        try:
            key_model = db.PocketStealthKeys.get(
                db.PocketStealthKeys.address == address)
        except db.DoesNotExist:
            return None
        return key_model.secret

    def key_from_address(self, address):
        secret = self._get_secret(address)
        if secret is not None:
            return secret
        stealth_secret = self._get_stealth_secret(address)
        if stealth_secret is not None:
            return stealth_secret
        return None

    @property
    def addrs(self):
        return self.addrs_normal + self.addrs_from_stealth

    @property
    def addrs_normal(self):
        rows = db.PocketKeys.select().where(
            db.PocketKeys.pocket == self._model)
        return [row.address for row in rows]

    @property
    def addrs_from_stealth(self):
        rows = db.PocketStealthKeys.select().where(
            db.PocketStealthKeys.pocket == self._model)
        return [row.address for row in rows]

    def address_index(self, address):
        try:
            key_model = db.PocketKeys.get(db.PocketKeys.address == address)
        except db.DoesNotExist:
            return None

        return key_model.index_

    @property
    def stealth_scan_private(self):
        return self._model.stealth_scan_key

    @property
    def stealth_spend_private(self):
        return self._model.stealth_spend_key

    @property
    def stealth_receiver(self):
        return StealthReceiver(self.stealth_scan_private,
                               self.stealth_spend_private,
                               self.address_version())

    def address_version(self):
        return self._model.account.payment_address_version()

    @property
    def stealth_address(self):
        return self.stealth_receiver.generate_stealth_address()

    def _stealth_key_entry_exists(self, address):
        try:
            db.PocketStealthKeys.get(db.PocketStealthKeys.address == address)
        except db.DoesNotExist:
            return False
        return True

    def add_stealth_key(self, address, key):
        if self._stealth_key_entry_exists(address):
            return
        db.PocketStealthKeys.create(pocket=self._model, address=address,
                                    secret=key)

    def number_normal_keys(self):
        return len(db.PocketKeys.select().where(
            db.PocketKeys.pocket == self._model))

    @property
    def history(self):
        return [HistoryRowModel(row) for row in self._model.history]

    def balance(self):
        return sum(row.value for row in self.history)

    @property
    def unspent_inputs(self):
        rows = db.History.select().where(db.History.spend == None,
                                         db.History.is_output == True,
                                         db.History.pocket == self._model)
        return [HistoryRowModel(row).to_input() for row in rows]

    @property
    def model(self):
        return self._model

    def pending_payments(self):
        pending = db.SentPayments.select().where(
            db.SentPayments.is_confirmed == False,
            db.SentPayments.pocket == self._model)
        return [PendingPaymentModel(payment) for payment in pending]

class CacheModel:

    def __init__(self, account_model):
        self._account_model = account_model

    @property
    def history(self):
        return HistoryModel(self._account_model)

    @property
    def transactions(self):
        return TransactionCacheModel(self._account_model)

class HistoryModel:

    def __init__(self, account_model):
        self._account_model = account_model

    def clear(self):
        account = self._account_model
        query = db.History.delete().where(db.History.account == account)
        query.execute()

    def __getitem__(self, address):
        rows = db.History.select().where(db.History.address == address)
        return [HistoryRowModel(row) for row in rows]

    def set(self, address, history, pocket):
        self._delete_entries(address, pocket)

        for output, spend in history:
            output_hash = bc.HashDigest.from_bytes(output[0].hash[::-1])

            value = output[2]
            output_value = Decimal(
                bc.encode_base10(value, bc.btc_decimal_places))

            if spend is None:
                spend = None
            else:
                spend_hash = bc.HashDigest.from_bytes(spend[0].hash[::-1])
                spend_value = -output_value

                spend = db.History.create(
                    account=self._account_model,
                    pocket=pocket.model,
                    address=address,

                    is_output=False,

                    hash=spend_hash,
                    index_=spend[0].index,
                    height=spend[1],

                    value=spend_value
                )

            db.History.create(
                account=self._account_model,
                pocket=pocket.model,
                address=address,

                is_output=True,
                spend=spend,

                hash=output_hash,
                index_=output[0].index,
                height=output[1],

                value=output_value
            )

    def _delete_entries(self, address, pocket):
        query = db.History.delete().where(db.History.address == address,
                                          db.History.pocket == pocket.model)
        query.execute()

    def __contains__(self, address):
        rows = db.History.select().where(db.History.address == address)
        return len(rows) > 0

    def values(self):
        return [[HistoryRowModel(row) for row in history]
                for history in self._model.values()]

    def all(self, from_height=0):
        all_rows = flatten(self.values())
        all_rows = [row for row in all_rows if row.height >= from_height]
        return all_rows

    @property
    def transaction_hashes(self):
        rows = db.History.select(db.History.hash)
        return [row.hash for row in rows]

class HistoryRowModel:

    def __init__(self, model):
        self._model = model

    @property
    def model(self):
        return self._model

    @property
    def is_output(self):
        return self._model.is_output

    @property
    def is_spend(self):
        return not self.is_output

    def is_spent_output(self):
        return self.is_output() and self.spend is not None

    def is_unspent_output(self):
        return self.is_output() and not self.is_spent_output()

    def is_change_output(self):
        if not self.is_output:
            return False
        try:
            db.History.get(db.History.hash == self.hash,
                           db.History.is_output == False,
                           db.History.pocket == self._model.pocket)
        except db.DoesNotExist:
            return False
        return True

    @property
    def hash(self):
        return self._model.hash

    @property
    def index(self):
        return self._model.index_

    @property
    def height(self):
        return self._model.height

    @property
    def address(self):
        return self._model.address

    def type_string(self):
        if self.is_output:
            return "output"
        elif self.is_spend:
            return "spend"
        assert False

    @property
    def value(self):
        value = self._model.value
        return decimal_to_satoshi(value)

    def value_minus_change(self):
        if self.is_output:
            return self.value
        return self.value + self._change_value()

    def _change_value(self):
        assert self.is_spend
        try:
            change_rows = db.History.select().where(
                db.History.hash == self.hash,
                db.History.is_output == True,
                db.History.pocket == self._model.pocket)
        except db.DoesNotExist:
            # No change output
            return 0
        return sum(HistoryRowModel(row).value for row in change_rows)

    @property
    def spend(self):
        spend = self._model.spend
        if spend is None:
            return spend
        return HistoryRowModel(spend)

    def to_input(self):
        assert self.is_output
        return (self.hash, self.index), self.value

class TransactionCacheModel:

    def __init__(self, model):
        self._model = model

    def __getitem__(self, tx_hash):
        if isinstance(tx_hash, bc.HashDigest):
            tx_hash = bc.encode_hash(tx_hash)
        tx = db.TransactionCache.get(db.TransactionCache.hash == tx_hash).tx
        assert tx.is_valid()
        return tx

    def __setitem__(self, tx_hash, tx):
        db.TransactionCache.create(
            hash=tx_hash,
            tx=tx
        )

    def __contains__(self, tx_hash):
        try:
            db.TransactionCache.get(db.TransactionCache.hash == tx_hash)
        except db.DoesNotExist:
            return False
        return True

class PendingPaymentModel:

    def __init__(self, model):
        self._model = model

    @property
    def tx_hash(self):
        return self._model.tx_hash

    @property
    def created_date(self):
        return self._model.created_date

    @property
    def destinations(self):
        return [(dest.address, dest.value) for dest
                in self._model.destinations]

class Account:

    def __init__(self, name, filename, context, settings):
        self.name = name
        self._context = context
        self._settings = settings

        self._model = AccountModel(filename)
        self.client = None

        self._scan_task = None
        self._updating_history = False

    def initialize_db(self, filename, password):
        db.initialize(filename, password)

    def brainwallet_wordlist(self):
        return self._model.wordlist

    def create(self, wordlist, is_testnet):
        ec = self._model.create(wordlist, is_testnet)
        if ec:
            return ec
        return None

    def save(self):
        #self._model.save(self._password)
        pass

    def load(self):
        return self._model.load()

    def stop(self):
        if self._scan_task is not None:
            self._scan_task.cancel()

    def start_scanning(self):
        self._connect()
        loop = asyncio.get_event_loop()
        self._scan_task = loop.create_task(self._check_updates())

    def _connect(self):
        client_settings = libbitcoin.server.ClientSettings()
        client_settings.query_expire_time = self._settings.query_expire_time
        client_settings.socks5 = self._settings.socks5
        url = self._settings.url
        if self._model.is_testnet:
            url = self._settings.testnet_url
        # Tornado implementation.
        if self._settings.use_tornado_impl:
            self.client = FakeAsyncClient(self._context, url, client_settings)
        else:
            self.client = Client(self._context, url, client_settings)
        print("Connected to %s" % url)

    async def _check_updates(self):
        self.current_height = None
        self.current_hash = None
        while True:
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
            self._updating_history = True
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
        print("Scanned.")
        await self._fill_cache()
        print("Cache filled.")
        await self._generate_keys()
        print("Updated.")

    def _finish_reorg(self, index):
        print("Updating current_index to:", index)
        self._model.current_index = index
        self._updating_history = False

    async def _sync_history(self, from_height):
        tasks = []
        for pocket in self._model.pockets:
            for address in pocket.addrs:
                tasks.append(self._scan(address, from_height, pocket))

        await asyncio.gather(*tasks)

    async def _scan(self, address, from_height, pocket):
        ec, history = await self.client.history(address.encoded())
        if ec:
            print("Couldn't fetch history:", ec, file=sys.stderr)
            return

        print("Fetching history for", address)
        self._model.cache.history.set(address, history, pocket)
        for output, spend in history:
            if spend is None:
                continue
            tx_hash = bc.HashDigest.from_bytes(spend[0].hash[::-1])
            self._model.mark_sent_transaction_confirmed(tx_hash)

    async def _fill_cache(self):
        for tx_hash in self._model.cache.history.transaction_hashes:
            if not tx_hash in self._model.cache.transactions:
                await self._grab_tx(tx_hash)

    async def _grab_tx(self, tx_hash):
        ec, tx_data = await self.client.transaction(tx_hash.data)
        if ec:
            print("Couldn't fetch transaction:", ec, file=sys.stderr)
            return
        print("Got tx:", tx_hash)
        tx = bc.Transaction.from_data(tx_data)
        self._model.cache.transactions[tx_hash] = tx

    async def _generate_keys(self):
        for pocket in self._model.pockets:
            self._generate_pocket_keys(pocket)

    def _generate_pocket_keys(self, pocket):
        max_i = -1
        for address in pocket.addrs:
            if address not in self._model.cache.history:
                continue
            i = pocket.address_index(address)
            if i is None:
                continue
            max_i = max(i, max_i)
        desired_len = max_i + 1 + self._settings.gap_limit
        remaining = desired_len - pocket.number_normal_keys()
        assert remaining >= 0
        for i in range(remaining):
            pocket.add_key()
        print("Generated %s keys" % remaining)

    async def _query_stealth(self, from_height):
        genesis_height = 0
        if self._model.is_testnet:
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

            version = self._model.payment_address_version()

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
        pocket = self._model.add_pocket(pocket_name)

        if pocket is None:
            return ErrorCode.duplicate

        self._generate_pocket_keys(pocket)
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
        return [str(address) for address in
                self._filter_unused(pocket.addrs_normal)]

    def is_used(self, addr):
        if addr in self._model.cache.history:
            return True
        return False

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
        if self._updating_history:
            return ErrorCode.updating_history, []

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
        if self._updating_history:
            return ErrorCode.updating_history, []

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

        history = []
        for row in pocket.history:
            if row.is_change_output():
                continue

            obj = {
                "hash": str(row.hash),
                "index": row.index,
                "height": row.height
            }

            row_json = {
                "addr": str(row.address),
                "type": row.type_string(),

                "spend": None,

                "value": row.value_minus_change()
            }

            if row.is_output:
                row_json["output"] = obj

                if row.spend is None:
                    row_json["spend"] = None
                else:
                    row_json["spend"] = {
                        "hash": str(row.spend.hash),
                        "index": row.spend.index,
                        "height": row.spend.height
                    }
            else:
                row_json["spend"] = obj

            history.append(row_json)

        return history

    async def get_height(self):
        return await self.client.last_height()

    def _is_correct_address(self, address):
        validator = AddressValidator(address)
        if not validator.is_valid():
            return False

        if validator.is_stealth():
            return True

        if self._model.is_testnet:
            if not validator.is_testnet():
                return False
        else:
            if not validator.is_mainnet():
                return False

        return validator.is_p2kh()

    async def send(self, dests, from_pocket, fee):
        if self._updating_history:
            return ErrorCode.updating_history, []

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
        if ec:
            return ec, None

        self._save_pending_transaction(dests, tx, from_pocket)

        return None, bc.encode_hash(tx.hash())

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
        if self._model.is_testnet:
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
        if self._model.is_testnet:
            p2kh = bc.PaymentAddress.testnet_p2kh
            p2sh = bc.PaymentAddress.testnet_p2sh
        return bc.PaymentAddress.extract(prevout_script, p2kh, p2sh)

    def _save_pending_transaction(self, dests, tx, from_pocket):
        pocket = self._model.pocket(from_pocket)
        self._model.save_pending_transaction(dests, tx, pocket)

    def pending_payments(self, pocket_name):
        if pocket_name is None:
            payments = self._model.all_pending_payments()
            payments = self._format_pending_payments(payments)
            return None, payments

        pocket = self._model.pocket(pocket_name)
        if pocket is None:
            return ErrorCode.not_found, []

        payments = pocket.pending_payments()
        payments = self._format_pending_payments(payments)

        return None, payments

    def _format_pending_payments(self, pending_payments):
        return [{
            "tx_hash": bc.encode_hash(payment.tx_hash),
            "created_date": payment.created_date.strftime("%d %b %Y"),
            "destinations": [
                (address, decimal_to_satoshi(value)) for address, value
                in payment.destinations
            ]
            } for payment in pending_payments]

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

    async def stop(self):
        self._account.stop()

    @property
    def accounts_path(self):
        return os.path.join(self._settings.config_path, "accounts")

    def _init_accounts_path(self):
        darkwallet.util.make_sure_dir_exists(self.accounts_path)

    def account_filename(self, account_name):
        return os.path.join(self.accounts_path, account_name)

    async def create_account(self, account_name, password, is_testnet):
        print("Create_account:", account_name, password)
        if account_name in self._account_names:
            return ErrorCode.duplicate, []

        # Create new seed
        wordlist = create_brainwallet_seed()
        print("Wordlist:", wordlist)

        if self._account is not None:
            self._account.stop()

        account_filename = self.account_filename(account_name)
        # Init current account object
        self._account = Account(account_name, account_filename,
                                self._context, self._settings)

        self._account.initialize_db(account_filename, password)
        ec = self._account.create(wordlist, is_testnet)
        if ec:
            self._account = None
            return ec, []

        # Create master pocket
        ec = self._account.create_pocket(self._settings.master_pocket_name)
        assert ec is None

        self._account_names.append(account_name)
        self._account.start_scanning()

        return None, []

    async def seed(self):
        if self._account is None:
            return ErrorCode.no_active_account_set, []
        return None, self._account.brainwallet_wordlist()

    async def restore_account(self, account_name, wordlist,
                              password, is_testnet):
        print("Restore_account:", account_name, wordlist, password)
        if account_name in self._account_names:
            return ErrorCode.duplicate, []

        if not bc.validate_mnemonic(wordlist):
            return ErrorCode.invalid_brainwallet, []

        if self._account is not None:
            self._account.stop()

        account_filename = self.account_filename(account_name)
        # Init current account object
        self._account = Account(account_name, account_filename,
                                self._context, self._settings)

        self._account.initialize_db(account_filename, password)
        ec = self._account.create(wordlist, is_testnet)
        if ec:
            self._account = None
            return ec, []

        # Create master pocket
        ec = self._account.create_pocket(self._settings.master_pocket_name)
        assert ec is None

        self._account_names.append(account_name)
        self._account.start_scanning()

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

        if self._account is not None:
            self._account.stop()

        account_filename = self.account_filename(account_name)
        # Init current account object
        self._account = Account(account_name, account_filename,
                                self._context, self._settings)

        self._account.initialize_db(account_filename, password)
        if not self._account.load():
            self._account = None
            return ErrorCode.wrong_password, []

        self._account.start_scanning()
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

    async def pending_payments(self, pocket):
        if self._account is None:
            return ErrorCode.no_active_account_set, []
        return self._account.pending_payments(pocket)

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
        loop = asyncio.get_event_loop()
        loop.stop()

