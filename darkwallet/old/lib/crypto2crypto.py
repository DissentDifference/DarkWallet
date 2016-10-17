import binascii
import json
import sys
import pyelliptic as ec

from darkwallet.lib.p2p import PeerConnection, TransportLayer
from multiprocessing import Process
import traceback

from darkwallet.lib.protocol import hello, response_pubkey
import libbitcoin

#if len(sys.argv) < 2:
#    print >> sys.stderr, "Error, you need the filename of your crypto stuff."
#    sys.exit(-1)

def load_crypto_details():
    with open(sys.argv[1]) as f:
        data = json.loads(f.read())
    assert "nickname" in data
    assert "secret" in data
    assert "pubkey" in data
    assert len(data["secret"]) == 2 * 32
    assert len(data["pubkey"]) == 2 * 33
    return data["nickname"], data["secret"].decode("hex"), data["pubkey"].decode("hex")

#NICKNAME, SECRET, PUBKEY = load_crypto_details()

class CryptoPeerConnection(PeerConnection):
    def __init__(self, address, transport, pub):
        self._priv = transport._myself
        self._pub = pub
        PeerConnection.__init__(self, transport, address)

    def encrypt(self, data):
        return self._priv.encrypt(data, self._pub)

    def send(self, data):
        self.send_raw(self.encrypt(json.dumps(data)))

    def on_message(self, msg):
        # this are just acks
        pass


def encode_hex(data):
    return binascii.hexlify(data).decode("ascii")

class CryptoTransportLayer(TransportLayer):
    def __init__(self, port=None, my_ip=None, net_ip=None):
        TransportLayer.__init__(self, port, my_ip, net_ip)
        self._myself = ec.ECC(curve='secp256k1')

        self.nick_mapping = {}

    def get_profile(self):
        peers = {}
        for uri, peer in self._peers.items():
            if peer._pub:
                peers[uri] = encode_hex(peer._pub)
        return {'uri': self._uri, 'pub': encode_hex(self._myself.get_pubkey()), 'peers': peers}

    def respond_pubkey_if_mine(self, nickname, ident_pubkey):
        if ident_pubkey != PUBKEY:
            print("Not my ident.")
            return
        pubkey = self._myself.get_pubkey()
        ec_key = libbitcoin.EllipticCurveKey()
        ec_key.set_secret(SECRET)
        digest = libbitcoin.Hash(pubkey)
        signature = ec_key.sign(digest)
        self.send(response_pubkey(nickname, pubkey, signature))

    def create_peer(self, uri, pub):
        if pub:
            self.log("init peer " + uri + " " + pub[0:8], '*')
            pub = pub.decode('hex')
        else:
            self.log("init peer [seed] " + uri, '*')

        # create the peer
        self._peers[uri] = CryptoPeerConnection(uri, self, pub)

        # call 'peer' callbacks on listeners
        self.trigger_callbacks('peer', self._peers[uri])

        # now send a hello message to the peer
        if pub:
            self.log("sending encrypted profile to %s" % uri)
            self._peers[uri].send(hello(self.get_profile()))
        else:
            # this is needed for the first connection
            self.log("sending  normal profile to %s" % uri)
            profile = hello(self.get_profile())
            self._peers[uri].send_raw(json.dumps(profile))

    def init_peer(self, msg):
        uri = msg['uri']
        pub = msg.get('pub')
        if uri == self._uri:
            return
        if not self.valid_peer_uri(uri):
            self.log("Error. Invalid Peer: %s " % uri)
            return
        if not uri in self._peers:
            self.create_peer(uri, pub)
        elif pub: # and not self._peers[uri]._pub:
            if self._peers[uri]._pub:
                self.log("updating peer pubkey " + uri)
            else:
                self.log("setting pub for seed node " + uri)
            if not self._peers[uri]._pub or not pub == encode_hex(self._peers[uri]._pub):
                self._peers[uri]._pub = pub.decode('hex')
                self._peers[uri].send(hello(self.get_profile()))

    def on_raw_message(self, serialized):
        try:
            msg = json.loads(serialized)
            self.log("receive [%s]" % msg.get('type', 'unknown'))
        except ValueError:
            try:
                msg = json.loads(self._myself.decrypt(serialized))
                self.log("decrypted [%s]" % msg.get('type', 'unknown'))
            except:
                self.log("incorrect msg ! %s...")
                traceback.print_exc()
                return

        msg_type = msg.get('type')
        if msg_type == 'hello' and msg.get('uri'):
            self.init_peer(msg)
            for uri, pub in msg.get('peers', {}).items():
                self.init_peer({'uri': uri, 'pub': pub})
            self.log("Update peer table [%s peers]" % len(self._peers))
        else:
            self.on_message(msg)


