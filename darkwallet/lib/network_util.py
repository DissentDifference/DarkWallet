import socket
from struct import unpack
import re


def is_loopback_addr(addr):
    return addr.startswith("127.0.0.") or addr == 'localhost'


def is_valid_port(port):
    return 0 < int(port) <= 65535


def is_valid_protocol(protocol):
    return protocol == 'tcp'


def is_valid_ip_address(addr):
    if addr == '0.0.0.0':
        return False
    try:
        socket.inet_aton(addr)
        return True
    except socket.error:
        return False


def is_private_ip_address(addr):
    if is_loopback_addr(addr):
        return True
    if not is_valid_ip_address(addr):
        return False
    # http://stackoverflow.com/questions/691045/how-do-you-determine-if-an-ip-address-is-private-in-python
    f = unpack('!I', socket.inet_pton(socket.AF_INET, addr))[0]
    private = (
        [2130706432, 4278190080],  # 127.0.0.0,   255.0.0.0   http://tools.ietf.org/html/rfc3330
        [3232235520, 4294901760],  # 192.168.0.0, 255.255.0.0 http://tools.ietf.org/html/rfc1918
        [2886729728, 4293918720],  # 172.16.0.0,  255.240.0.0 http://tools.ietf.org/html/rfc1918
        [167772160, 4278190080],  # 10.0.0.0,    255.0.0.0   http://tools.ietf.org/html/rfc1918
    )
    for net in private:
        if f & net[1] == net[0]:
            return True
    return False


def uri_parts(uri):
    m = re.match(r"(\w+)://([\w\.]+):(\d+)", uri)
    if m is not None:
        return m.group(1), m.group(2), m.group(3)
    else:
        raise RuntimeError('URI is not valid')
