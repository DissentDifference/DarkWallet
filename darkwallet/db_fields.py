from libbitcoin import bc

from playhouse.sqlcipher_ext import *

class HashDigestField(Field):
    db_field = "hash_digest"

    def db_value(self, value):
        if isinstance(value, str):
            return value
        return bc.encode_hash(value)

    def python_value(self, value):
        if value is None:
            return None
        return bc.hash_literal(value)

class WordListField(Field):
    db_field = "word_list"

    def db_value(self, words):
        value = ", ".join(words)
        return value

    def python_value(self, value):
        words = value.split(", ")
        return words

class TransactionField(Field):
    db_field = "chain_transaction"

    def db_value(self, tx):
        return tx.to_data().hex()

    def python_value(self, tx_data):
        tx_data = bytes.fromhex(tx_data)
        tx = bc.Transaction.from_data(tx_data)
        assert tx is not None
        return tx

class PaymentAddressField(Field):
    db_field = "payment_address"

    def db_value(self, address):
        return str(address)

    def python_value(self, address):
        address = bc.PaymentAddress.from_string(address)
        assert address is not None
        return address

class StealthAddressField(Field):
    db_field = "stealth_address"

    def db_value(self, address):
        return str(address)

    def python_value(self, address):
        address = bc.StealthAddress.from_string(address)
        assert address is not None
        return address

class HdPrivateField(Field):
    db_field = "hd_private"

    def db_value(self, key):
        return str(key)

    def python_value(self, key):
        key = bc.HdPrivate.from_string(key)
        assert key is not None
        return key

class EcSecretField(Field):
    db_field = "ec_secret"

    def db_value(self, secret):
        return str(secret)

    def python_value(self, secret):
        return bc.EcSecret.from_string(secret)

class BitcoinValueField(DecimalField):
    def __init__(self):
        super().__init__(max_digits=16, decimal_places=8,
                         constraints=[Check(
                             "value < 20999999.9769 and "
                             "value > -20999999.9769")])

