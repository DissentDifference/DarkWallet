from enum import Enum
from libbitcoin import bc

class AddressType(Enum):
    mainnet_p2kh = 1
    mainnet_p2sh = 2
    testnet_p2kh = 3
    testnet_p2sh = 4
    other_payment = 5
    stealth = 6
    invalid = 7

class AddressValidator:

    def __init__(self, address):
        self._address = address

    def is_valid(self):
        return self.type() != AddressType.invalid

    def is_mainnet(self):
        return (self.type() == AddressType.mainnet_p2kh or
                self.type() == AddressType.mainnet_p2sh)

    def is_testnet(self):
        return (self.type() == AddressType.testnet_p2kh or
                self.type() == AddressType.testnet_p2sh)

    def is_payment(self):
        return (self.is_mainnet() or self.is_testnet() or
                self.type() == AddressType.other_payment)

    def is_stealth(self):
        return self.type() == AddressType.stealth

    def type(self):
        if self.payment_address is not None:
            payaddr = self.payment_address
            if payaddr.version() == bc.PaymentAddress.mainnet_p2kh:
                return AddressType.mainnet_p2kh
            elif payaddr.version() == bc.PaymentAddress.mainnet_p2sh:
                return AddressType.mainnet_p2sh
            elif payaddr.version() == bc.PaymentAddress.testnet_p2kh:
                return AddressType.testnet_p2kh
            elif payaddr.version() == bc.PaymentAddress.testnet_p2sh:
                return AddressType.testnet_p2sh
            else:
                return AddressType.other_payment
        elif self.stealth_address is not None:
            return AddressType.stealth
        return AddressType.invalid

    @property
    def payment_address(self):
        return bc.PaymentAddress.from_string(self._address)

    @property
    def stealth_address(self):
        return bc.StealthAddress.from_string(self._address)

