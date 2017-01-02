import os
from libbitcoin import bc

class StealthReceiver:

    def __init__(self, scan_private, spend_private,
                 version=bc.PaymentAddress.mainnet_p2kh):
        self.scan_private = scan_private
        self.spend_private = spend_private
        self._version = version

    def generate_stealth_address(self):
        # Receiver generates a new scan private.
        scan_public = self.scan_private.to_public()

        # Receiver generates a new spend private.
        spend_public = self.spend_private.to_public()

        stealth_addr = bc.StealthAddress.from_tuple(
            None, scan_public, [spend_public])

        return stealth_addr

    def derive_address(self, ephemeral_public):
        spend_public = self.spend_private.to_public()
        self.receiver_public = bc.uncover_stealth(
            ephemeral_public, self.scan_private, spend_public)

        if self.receiver_public is None:
            return None

        self.derived_address = bc.PaymentAddress.from_point(
            self.receiver_public, self._version)
        return self.derived_address

    def derive_private(self, ephemeral_public):
        receiver_private = bc.uncover_stealth(
            ephemeral_public, self.scan_private, self.spend_private)
        return receiver_private

class StealthSender:

    def __init__(self, version=bc.PaymentAddress.mainnet_p2kh):
        self._version = version

    @staticmethod
    def _random_data(size):
        return os.urandom(size)

    @staticmethod
    def _random_ephemeral_secret():
        seed = StealthSender._random_data(bc.EcSecret.size)
        secret = bc.create_ephemeral_key(seed)
        assert secret is not None
        return secret

    def send_to_stealth_address(self, stealth_addr, ephemeral_private=None):
        if isinstance(stealth_addr, str):
            stealth_addr = bc.StealthAddress.from_string(stealth_addr)
            assert stealth_addr is not None

        # Sender generates a new ephemeral key.
        if ephemeral_private is None:
            ephemeral_private = StealthSender._random_ephemeral_secret()
        ephemeral_public = ephemeral_private.to_public()

        spend_keys = stealth_addr.spend_keys()
        assert spend_keys

        # Sender derives stealth public, requiring ephemeral private.
        self.sender_public = bc.uncover_stealth(stealth_addr.scan_key(),
                                           ephemeral_private,
                                           spend_keys[0])
        self._send_address = bc.PaymentAddress.from_point(
            self.sender_public, self._version)

        metadata = ephemeral_public.data[1:]
        assert len(metadata) == 32
        meta_script = bc.Script.from_ops([
            bc.Opcode.return_,
            metadata + StealthSender._random_data(8)
        ])
        return meta_script, self._send_address

