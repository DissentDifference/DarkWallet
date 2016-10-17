import binascii

def encode_hex(value):
    return binascii.hexlify(value).decode("ascii")

