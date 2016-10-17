#!/usr/bin/python3
import argparse
import asyncio
import getpass
import json
import random
import sys
import websockets

def enter_confirmed_password():
    password = getpass.getpass()
    confirm_password = getpass.getpass("Confirm password:")
    if password != confirm_password:
        return None
    return password

def create_random_id():
    MAX_UINT32 = 4294967295
    return random.randint(0, MAX_UINT32)

async def init(args):
    assert args.account
    account = args.account[0]
    password = enter_confirmed_password()
    if password is None:
        print("Passwords don't match.")
        return -1
    message = json.dumps({
        "command": "dw_create_account",
        "id": create_random_id(),
        "params": [
            account,
            password
        ]
    })
    print("Sending:", message)
    async with websockets.connect('ws://localhost:8888') as websocket:
        await websocket.send(message)
        response = json.loads(await websocket.recv())
    print(response)
    return 0

async def restore(args):
    assert args.account
    account = args.account[0]
    brainwallet = input("Brainwallet: ")
    password = enter_confirmed_password()
    if password is None:
        print("Passwords don't match.")
        return -1
    message = json.dumps({
        "command": "dw_restore_account",
        "id": create_random_id(),
        "params": [
            account,
            brainwallet,
            password
        ]
    })
    print("Sending:", message)
    return 0

async def balance(args):
    message = json.dumps({
        "command": "dw_balance",
        "id": create_random_id(),
        "params": [
            args.pocket
        ]
    })
    print("Sending:", message)
    return 0

async def history(args):
    message = json.dumps({
        "command": "dw_history",
        "id": create_random_id(),
        "params": [
            args.pocket
        ]
    })
    print("Sending:", message)
    return 0

async def account(args):
    message = json.dumps({
        "command": "dw_list_accounts",
        "id": create_random_id(),
        "params": [
        ]
    })
    print("Sending:", message)
    return 0

async def dw_set(args):
    assert args.account
    account = args.account[0]
    password = getpass.getpass()
    message = json.dumps({
        "command": "dw_set_account",
        "id": create_random_id(),
        "params": [
            account,
            password
        ]
    })
    print("Sending:", message)
    return 0

async def rm(args):
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
    return 0

async def pocket(args):
    if args.pocket is None and args.delete:
        print("Need a pocket specified when deleting a pocket.",
              file=sys.stderr)
        return -1
    if args.pocket is None:
        message = json.dumps({
            "command": "dw_list_pockets",
            "id": create_random_id(),
            "params": [
            ]
        })
    elif args.delete:
        message = json.dumps({
            "command": "dw_delete_pocket",
            "id": create_random_id(),
            "params": [
                args.pocket
            ]
        })
    else:
        message = json.dumps({
            "command": "dw_create_pocket",
            "id": create_random_id(),
            "params": [
                args.pocket
            ]
        })
    print("Sending:", message)
    return 0

async def send(args):
    assert args.address
    assert args.amount
    address = args.address[0]
    amount = args.amount[0]
    message = json.dumps({
        "command": "dw_send",
        "id": create_random_id(),
        "params": [
            args.pocket,
            [(address, amount)]
        ]
    })
    print("Sending:", message)
    return 0

async def recv(args):
    message = json.dumps({
        "command": "dw_receive",
        "id": create_random_id(),
        "params": [
            args.pocket
        ]
    })
    print("Sending:", message)
    return 0

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
    parser_init.set_defaults(func=init)

    parser_restore = subparsers.add_parser("restore",
                                           help="Restore an account.")
    parser_restore.add_argument("account", nargs=1, metavar="ACCOUNT",
                                help="Account name")
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
    parser_send.add_argument("pocket", nargs="?", metavar="POCKET",
                             default=None, help="Pocket name to send from")
    parser_send.add_argument("address", nargs=1, metavar="ADDRESS",
                             help="Address for send in the format")
    parser_send.add_argument("amount", nargs=1, metavar="AMOUNT",
                             help="Amount for send in the format")
    parser_send.set_defaults(func=send)

    parser_recv = subparsers.add_parser("recv", help="Receive Bitcoins")
    parser_recv.add_argument("pocket", nargs="?", metavar="POCKET",
                             default=None, help="Pocket name")
    parser_recv.set_defaults(func=recv)

    parser.set_defaults(func=None)
    args = parser.parse_args()
    if args.func is None:
        parser.print_help()
        return -1
    return await args.func(args)

asyncio.get_event_loop().run_until_complete(main())

