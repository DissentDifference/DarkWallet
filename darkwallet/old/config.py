import json
with open('config.json') as f:
    config = json.load(f);

def get(name, default=None):
    return config.get(name, default)
