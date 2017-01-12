#!/usr/bin/python3
import argparse
import asyncio
import getpass
import json
import random
import sys
import websockets

# Our modules
import api

def enter_confirmed_password():
    password = getpass.getpass()
    confirm_password = getpass.getpass("Confirm password:")
    if password != confirm_password:
        return None
    return password

async def init(args, websockets_path):
    assert args.account
    account_name = args.account[0]

    #password = enter_confirmed_password()
    password = "surfing2"
    if password is None:
        print("Error: passwords don't match.", file=sys.stderr)
        return -1

    is_testnet = args.testnet

    async with api.WebSocket(websockets_path) as ws:
        ec = await api.Account.create(ws, account_name,
                                      password, is_testnet)

    if ec:
        print("Error: failed to create account.", ec, file=sys.stderr)
        return -1

    print("Account created.")
    return 0

async def seed(args, websockets_path):
    async with api.WebSocket(websockets_path) as ws:
        ec, seed = await api.Account.seed(ws)

    if ec:
        print("Error: failed to get seed.", ec, file=sys.stderr)
        return -1

    print(" ".join(seed))
    return 0

async def restore(args, websockets_path):
    assert args.account
    account = args.account[0]
    #brainwallet = input("Brainwallet: ").split(" ")
    brainwallet = ['install', 'oppose', 'unique', 'steel', 'opera', 'next',
                   'add', 'town', 'warfare', 'leave', 'salt', 'chimney']
    #password = enter_confirmed_password()
    password = "surfing2"
    if password is None:
        print("Passwords don't match.")
        return -1
    message = json.dumps({
        "command": "dw_restore_account",
        "id": create_random_id(),
        "params": [
            account,
            brainwallet,
            password,
            args.testnet
        ]
    })
    print("Sending:", message)
    async with websockets.connect(websockets_path) as websocket:
        await websocket.send(message)
        response = json.loads(await websocket.recv())
    print(response)
    return 0

async def balance(args, websockets_path):
    async with api.WebSocket(websockets_path) as ws:
        ec, balance = await api.Wallet.balance(ws, args.pocket)
    if ec:
        print("Error: fetching balance.", ec, file=sys.stderr)
        return
    print(balance)
    return 0

async def history(args, websockets_path):
    async with api.WebSocket(websockets_path) as ws:
        ec, history = await api.Wallet.history(ws, args.pocket)
    if ec:
        print("Error: fetching history.", ec, file=sys.stderr)
        return
    print(json.dumps(history, indent=2))
    return 0

async def account(args, websockets_path):
    async with api.WebSocket(websockets_path) as ws:
        active_account, account_names = await api.Account.list(ws)

    for name in account_names:
        if name == active_account:
            print("*", name)
        else:
            print(" ", name)
    return 0

async def dw_set(args, websockets_path):
    assert args.account
    account_name = args.account[0]

    #password = getpass.getpass()
    password = "surfing2"

    async with api.WebSocket(websockets_path) as ws:
        ec = await api.Account.set(ws, account_name, password)

    return 0

async def rm(args, websockets_path):
    assert args.account
    account = args.account[0]
    message = json.dumps({
        "command": "dw_delete_account",
        "id": create_random_id(),
        "params": [
            account
        ]
    })
    print("Sending:", message)
    async with websockets.connect(websockets_path) as websocket:
        await websocket.send(message)
        response = json.loads(await websocket.recv())
    print(response)
    return 0

async def pocket(args, websockets_path):
    if args.pocket is None and args.delete:
        print("Need a pocket specified when deleting a pocket.",
              file=sys.stderr)
        return -1
    if args.pocket is None:
        async with api.WebSocket(websockets_path) as ws:
            ec, pockets = await api.Pocket.list(ws)
        if ec:
            print("Error: unable to fetch pockets.", ec, file=sys.stderr)
            return
        for pocket in pockets:
            print(pocket)
    elif args.delete:
        message = json.dumps({
            "command": "dw_delete_pocket",
            "id": create_random_id(),
            "params": [
                args.pocket
            ]
        })
    else:
        async with api.WebSocket(websockets_path) as ws:
            ec = await api.Pocket.create(ws, args.pocket)
        if ec:
            print("Error: unable to create pocket.", ec, file=sys.stderr)
            return
        print("Pocket created.")
    return 0

async def send(args, websockets_path):
    assert args.address
    assert args.amount
    address = args.address[0]
    amount = args.amount[0]
    dests = [(address, amount)]
    async with api.WebSocket(websockets_path) as ws:
        ec, tx_hash = await api.Wallet.send(ws, dests, args.pocket, args.fee)
    if ec:
        print("Error: sending funds.", ec, file=sys.stderr)
        return
    print(tx_hash)
    return 0

async def recv(args, websockets_path):
    async with api.WebSocket(websockets_path) as ws:
        ec, addrs = await api.Wallet.receive(ws, args.pocket)
    if ec:
        print("Error: fetching receive addresses.", ec, file=sys.stderr)
        return
    for addr in addrs:
        print(addr)
    return 0

async def stealth(args, websockets_path):
    async with api.WebSocket(websockets_path) as ws:
        ec, stealth_addr = await api.Wallet.stealth(ws, args.pocket)
    if ec:
        print("Error: fetching receive addresses.", ec, file=sys.stderr)
        return
    print(stealth_addr)
    return 0

async def valid_addr(args, websockets_path):
    assert args.address
    message = json.dumps({
        "command": "dw_validate_address",
        "id": create_random_id(),
        "params": [
            args.address[0]
        ]
    })
    print("Sending:", message)
    async with websockets.connect(websockets_path) as websocket:
        await websocket.send(message)
        response = json.loads(await websocket.recv())
    print(response)
    return 0

async def get_height(args, websockets_path):
    message = json.dumps({
        "command": "dw_get_height",
        "id": api.create_random_id(),
        "params": [
        ]
    })
    print("Sending:", message)
    async with websockets.connect(websockets_path) as websocket:
        await websocket.send(message)
        response = json.loads(await websocket.recv())
    print(response)
    return 0

async def setting(args, websockets_path):
    name = args.name[0]
    value = args.value
    if value is None:
        message = json.dumps({
            "command": "dw_get_setting",
            "id": create_random_id(),
            "params": [
                name
            ]
        })
    else:
        message = json.dumps({
            "command": "dw_set_setting",
            "id": create_random_id(),
            "params": [
                name,
                value
            ]
        })
    print("Sending:", message)
    async with websockets.connect(websockets_path) as websocket:
        await websocket.send(message)
        response = json.loads(await websocket.recv())
    print(response)

async def stop(args, websockets_path):
    async with api.WebSocket(websockets_path) as ws:
        await api.Daemon.stop(ws)

async def main():
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
    parser_init.add_argument("--testnet", "-t", dest="testnet",
        action="store_const", const=True, default=False,
        help="Create a testnet account")
    parser_init.set_defaults(func=init)

    parser_seed = subparsers.add_parser("seed",
                                        help="Show brainwallet seed.")
    parser_seed.set_defaults(func=seed)

    parser_restore = subparsers.add_parser("restore",
                                           help="Restore an account.")
    parser_restore.add_argument("account", nargs=1, metavar="ACCOUNT",
                                help="Account name")
    parser_restore.add_argument("--testnet", "-t", dest="testnet",
        action="store_const", const=True, default=False,
        help="Create a testnet account")
    parser_restore.set_defaults(func=restore)

    parser_balance = subparsers.add_parser("balance", help="Show balance")
    parser_balance.add_argument("pocket", nargs="?", metavar="POCKET",
                                default=None, help="Pocket name")
    parser_balance.set_defaults(func=balance)

    parser_history = subparsers.add_parser("history", help="Show history")
    parser_history.add_argument("pocket", nargs="?", metavar="POCKET",
                                default=None, help="Pocket name")
    parser_history.set_defaults(func=history)

    parser_account = subparsers.add_parser("account", help="List accounts")
    parser_account.set_defaults(func=account)

    parser_set = subparsers.add_parser("set", help="Switch to an account")
    parser_set.add_argument("account", nargs=1, metavar="ACCOUNT",
                            help="Account name")
    parser_set.set_defaults(func=dw_set)

    parser_rm = subparsers.add_parser("rm", help="Remove an account")
    parser_rm.add_argument("account", nargs=1, metavar="ACCOUNT",
                           help="Account name")
    parser_rm.set_defaults(func=rm)

    parser_pocket = subparsers.add_parser("pocket",
        help="List, create or delete pockets")
    parser_pocket.add_argument("pocket", nargs="?", metavar="POCKET",
                               default=None, help="Pocket name")
    parser_pocket.add_argument("--delete", "-d", dest="delete",
        action="store_const", const=True, default=False,
        help="Delete a pocket")
    parser_pocket.set_defaults(func=pocket)

    parser_send = subparsers.add_parser("send", help="Send Bitcoins")
    parser_send.add_argument("address", nargs=1, metavar="ADDRESS",
                             help="Address for send in the format")
    parser_send.add_argument("amount", nargs=1, metavar="AMOUNT",
                             help="Amount for send in the format")
    parser_send.add_argument("--pocket", "-p", dest="pocket",
                             help="Pocket name to send from", default=None)
    parser_send.add_argument("--fee", "-f", dest="fee", type=int,
                             help="Fee to pay", default=0)
    parser_send.set_defaults(func=send)

    parser_recv = subparsers.add_parser("recv", help="Receive Bitcoins")
    parser_recv.add_argument("pocket", nargs="?", metavar="POCKET",
                             default=None, help="Pocket name")
    parser_recv.set_defaults(func=recv)

    parser_stealth = subparsers.add_parser("stealth",
                                           help="Show stealth address")
    parser_stealth.add_argument("pocket", nargs="?", metavar="POCKET",
                             default=None, help="Pocket name")
    parser_stealth.set_defaults(func=stealth)

    parser_valid_addr = subparsers.add_parser("validate_address",
        help="Validate a Bitcoin address")
    parser_valid_addr.add_argument("address", nargs=1, metavar="ADDRESS",
                             help="Address for send in the format")
    parser_valid_addr.set_defaults(func=valid_addr)

    parser_get_height = subparsers.add_parser("get_height",
        help="Get height of the last block")
    parser_get_height.set_defaults(func=get_height)

    parser_setting = subparsers.add_parser("setting",
                                           help="Get and set a setting")
    parser_setting.add_argument("name", nargs=1, metavar="NAME",
                                default=None, help="Setting name")
    parser_setting.add_argument("value", nargs="?", metavar="VALUE",
                                default=None, help="Setting value")
    parser_setting.set_defaults(func=setting)

    parser_help = subparsers.add_parser("stop", help="Stop the daemon")
    parser_help.set_defaults(func=stop)

    parser_help = subparsers.add_parser("help", help="Show help")
    parser_help.set_defaults(func=None)

    parser.set_defaults(func=None)
    args = parser.parse_args()
    if args.func is None:
        parser.print_help()
        return -1
    port = args.port
    if port is None:
        port = 8888
    websockets_path = "ws://localhost:%s" % port
    return await args.func(args, websockets_path)

asyncio.get_event_loop().run_until_complete(main())

