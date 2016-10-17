

def hello(data):
    data['type'] = 'hello'
    return data

def ok():
    return {'type': 'ok'}

def response_pubkey(nickname, pubkey, signature):
    data = {}
    data['type'] = "response_pubkey"
    data['nickname'] = nickname
    data['pubkey'] = pubkey.encode("hex")
    data['signature'] = signature.encode("hex")
    return data

