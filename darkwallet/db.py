import datetime
from enum import Enum
from playhouse.sqlcipher_ext import *
from darkwallet.db_fields import *

db = SqlCipherDatabase(None)

class Error(Enum):
    short_password = 0

class BaseModel(Model):
    class Meta:
        database = db

class Account(BaseModel):
    wordlist = WordListField()
    is_testnet = BooleanField()
    current_height = IntegerField(null=True, default=None)
    current_hash = HashDigestField(null=True, default=None)

    def payment_address_version(self):
        if self.is_testnet:
            return bc.PaymentAddress.testnet_p2kh
        return bc.PaymentAddress.mainnet_p2kh

class Pocket(BaseModel):
    account = ForeignKeyField(Account, related_name="pockets")
    name = CharField(unique=True)

    index_ = IntegerField()
    main_key = HdPrivateField()

    stealth_address = StealthAddressField()
    stealth_scan_key = EcSecretField()
    stealth_spend_key = EcSecretField()

    @property
    def is_testnet(self):
        return self.account.is_testnet

class PocketKeys(BaseModel):
    pocket = ForeignKeyField(Pocket, related_name="keys")
    index_ = IntegerField()
    address = PaymentAddressField(index=True)
    key = HdPrivateField()

    @property
    def secret(self):
        return self.key.secret()

class PocketStealthKeys(BaseModel):
    pocket = ForeignKeyField(Pocket, related_name="stealth_keys")
    address = PaymentAddressField(index=True)
    secret = EcSecretField()

class TransactionCache(BaseModel):
    hash = HashDigestField(unique=True)
    tx = TransactionField()

class History(BaseModel):
    account = ForeignKeyField(Account, related_name="history")
    pocket = ForeignKeyField(Pocket, related_name="history")
    address = PaymentAddressField(index=True)

    is_output = BooleanField()

    @property
    def is_spend(self):
        return not self.is_output

    spend = ForeignKeyField("self", null=True)

    hash = HashDigestField()
    index_ = IntegerField()
    height = IntegerField()

    value = BitcoinValueField()

class SentPayments(BaseModel):
    tx_hash = HashDigestField(unique=True)
    tx = TransactionField()
    replaced_by = ForeignKeyField("self", null=True, default=None)
    is_confirmed = BooleanField(default=False)
    created_date = DateTimeField(default=datetime.datetime.now)

    account = ForeignKeyField(Account, related_name="sent_payments")
    pocket = ForeignKeyField(Pocket, null=True, related_name="sent_payments")

class SentPaymentDestinations(BaseModel):
    parent = ForeignKeyField(SentPayments, related_name="destinations")
    address = CharField(index=True)
    value = BitcoinValueField()

def initialize(filename, passphrase):
    db.init(filename, passphrase=passphrase)

def create_tables():
    db.create_tables([
        Account,
        Pocket,
        PocketKeys,
        PocketStealthKeys,
        TransactionCache,
        History,
        SentPayments,
        SentPaymentDestinations
    ])

