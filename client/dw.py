#!/usr/bin/python3
import argparse
import asyncio
import json
import sys
import websockets

async def test_fetch_last_height(websocket):
    print("Testing fetch last_height...")

    message = json.dumps({
        "command": "fetch_last_height",
        "id": 1,
        "params": [
        ]
    }, indent=2)
    print("Sending:", message)
    await websocket.send(message)

    response = json.loads(await websocket.recv())
    print(json.dumps(response, indent=2))
    print()

async def test_fetch_transaction(websocket):
    print("Testing fetch transaction...")

    message = json.dumps({
        "command": "fetch_transaction",
        "id": 1,
        "params": [
            "ee475443f1fbfff84ffba43ba092a70d291df233bd1428f3d09f7bd1a6054a1f"
        ]
    }, indent=2)
    print("Sending:", message)
    await websocket.send(message)

    response = json.loads(await websocket.recv())
    print(json.dumps(response, indent=2))
    print()

async def test_fetch_history(websocket):
    print("Testing fetch history...")

    message = json.dumps({
        "command": "fetch_history",
        "id": 1,
        "params": [
            "13ejSKUxLT9yByyr1bsLNseLbx9H9tNj2d"
        ]
    }, indent=2)
    print("Sending:", message)
    await websocket.send(message)

    response = json.loads(await websocket.recv())
    print(json.dumps(response, indent=2))
    print()

async def test_fetch_block_header(websocket):
    print("Testing fetch block_header...")

    message = json.dumps({
        "command": "fetch_block_header",
        "id": 1,
        "params": [
            "000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f"
        ]
    }, indent=2)
    print("Sending:", message)
    await websocket.send(message)

    response = json.loads(await websocket.recv())
    print(json.dumps(response, indent=2))
    print()

async def test_fetch_block_transaction_hashes(websocket):
    print("Testing fetch block_transaction_hashes...")

    message = json.dumps({
        "command": "fetch_block_transaction_hashes",
        "id": 1,
        "params": [
            "000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f"
        ]
    }, indent=2)
    print("Sending:", message)
    await websocket.send(message)

    response = json.loads(await websocket.recv())
    print(json.dumps(response, indent=2))
    print()

async def test_fetch_spend(websocket):
    print("Testing fetch spend...")

    message = json.dumps({
        "command": "fetch_spend",
        "id": 1,
        "params": [
            ("0530375a5bf4ea9a82494fcb5ef4a61076c2af807982076fa810851f4bc31c09",
             0)
        ]
    }, indent=2)
    print("Sending:", message)
    await websocket.send(message)

    response = json.loads(await websocket.recv())
    print(json.dumps(response, indent=2))
    print()

async def test_fetch_transaction_index(websocket):
    print("Testing fetch transaction_index...")

    message = json.dumps({
        "command": "fetch_transaction_index",
        "id": 1,
        "params": [
            "ee475443f1fbfff84ffba43ba092a70d291df233bd1428f3d09f7bd1a6054a1f"
        ]
    }, indent=2)
    print("Sending:", message)
    await websocket.send(message)

    response = json.loads(await websocket.recv())
    print(json.dumps(response, indent=2))
    print()

async def test_fetch_block_height(websocket):
    print("Testing fetch block_height...")

    message = json.dumps({
        "command": "fetch_block_height",
        "id": 1,
        "params": [
            "000000000000048b95347e83192f69cf0366076336c639f9b7228e9ba171342e"
        ]
    }, indent=2)
    print("Sending:", message)
    await websocket.send(message)

    response = json.loads(await websocket.recv())
    print(json.dumps(response, indent=2))
    print()

async def test_fetch_stealth(websocket):
    print("Testing fetch stealth...")

    message = json.dumps({
        "command": "fetch_stealth",
        "id": 1,
        "params": [
            "11", 419135
        ]
    }, indent=2)
    print("Sending:", message)
    await websocket.send(message)

    response = json.loads(await websocket.recv())
    print(json.dumps(response, indent=2))
    print()

async def test_ticker(websocket):
    print("Testing ticker...")

    message = json.dumps({
        "command": "fetch_ticker",
        "id": 1,
        "params": [
            "USD"
        ]
    })
    print("Sending:", message)
    await websocket.send(message)

    response = json.loads(await websocket.recv())
    print(json.dumps(response, indent=2))
    print()

async def test_broadcast(websocket):
    print("Testing broadcast...")

    # ee475443f1fbfff84ffba43ba092a70d291df233bd1428f3d09f7bd1a6054a1f
    message = json.dumps({
        "command": "broadcast",
        "id": 1,
        "params": [
            "010000000110ee96aa946338cfd0b2ed0603259cfe2f5458c32ee4bd7b88b583769c6b046e010000006b483045022100e5e4749d539a163039769f52e1ebc8e6f62e39387d61e1a305bd722116cded6c022014924b745dd02194fe6b5cb8ac88ee8e9a2aede89e680dcea6169ea696e24d52012102b4b754609b46b5d09644c2161f1767b72b93847ce8154d795f95d31031a08aa2ffffffff028098f34c010000001976a914a134408afa258a50ed7a1d9817f26b63cc9002cc88ac8028bb13010000001976a914fec5b1145596b35f59f8be1daf169f375942143388ac00000000"
        ]
    })
    print("Sending:", message)
    await websocket.send(message)

    while True:
        response = json.loads(await websocket.recv())
        print(json.dumps(response, indent=2))

async def hello():
    async with websockets.connect('ws://localhost:8888') as websocket:
        await test_fetch_last_height(websocket)
        #await test_fetch_transaction(websocket)
        #await test_fetch_history(websocket)
        #await test_fetch_block_header(websocket)
        #await test_fetch_block_transaction_hashes(websocket)
        #await test_fetch_spend(websocket)
        #await test_fetch_transaction_index(websocket)
        #await test_fetch_block_height(websocket)
        #await test_fetch_stealth(websocket)
        #await test_ticker(websocket)
        #await test_broadcast(websocket)

def main():
    # Command line arguments
    parser = argparse.ArgumentParser(prog="dw")
    parser.add_argument("--version", "-v", action="version",
                        version="%(prog)s 2.0")
    parser.add_argument("--port", "-p", dest="port",
                        help="Connect to daemon on the given port.",
                        default=None)
    subparsers = parser.add_subparsers(help="sub-command help")

    parser_init = subparsers.add_parser("init", help="Create new account.")
    parser_init.add_argument("account", nargs=1, metavar="ACCOUNT",
                             help="Account name")

    parser_restore = subparsers.add_parser("restore",
                                           help="Restore an account.")
    parser_restore.add_argument("account", nargs=1, metavar="ACCOUNT",
                                help="Account name")

    parser_balance = subparsers.add_parser("balance", help="Show balance")
    parser_balance.add_argument("pocket", nargs="?", metavar="POCKET",
                                default=None, help="Pocket name")

    parser_history = subparsers.add_parser("history", help="Show history")
    parser_history.add_argument("pocket", nargs="?", metavar="POCKET",
                                default=None, help="Pocket name")

    parser_account = subparsers.add_parser("account", help="List accounts")

    parser_set = subparsers.add_parser("set", help="Switch to an account")
    parser_set.add_argument("account", nargs=1, metavar="ACCOUNT",
                            help="Account name")

    parser_rm = subparsers.add_parser("rm", help="Remove an account")
    parser_rm.add_argument("account", nargs=1, metavar="ACCOUNT",
                           help="Account name")

    parser_pocket = subparsers.add_parser("pocket",
        help="List, create or delete pockets")
    parser_pocket.add_argument("pocket", nargs="?", metavar="POCKET",
                               default=None, help="Pocket name")
    parser_pocket.add_argument("--delete", "-d", dest="delete", nargs=1,
                               help="Delete a pocket")

    parser_send = subparsers.add_parser("send", help="Send Bitcoins")
    parser_send.add_argument("pocket", nargs="?", metavar="POCKET",
                             default=None, help="Pocket name")
    parser_send.add_argument("destinations", nargs="+", metavar="DESTINATIONS",
                             help="Destinations for send in the format of " \
                                  "ADDRESS:AMOUNT")

    parser_recv = subparsers.add_parser("recv", help="Receive Bitcoins")
    parser_recv.add_argument("pocket", nargs="?", metavar="POCKET",
                             default=None, help="Pocket name")

    args = parser.parse_args()
    return 0

if __name__ == "__main__":
    sys.exit(main())

asyncio.get_event_loop().run_until_complete(hello())

