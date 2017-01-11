#!/usr/bin/python3
import asyncio
import enum
import json
import random
import sys
import traceback
import websockets
from decimal import Decimal

class ErrorCode(enum.Enum):
    wrong_password = 1
    invalid_brainwallet = 2
    no_active_account_set = 3
    duplicate = 4
    not_found = 5
    not_enough_funds = 6
    invalid_address = 7
    short_password = 8
    updating_history = 9

def create_random_id():
    MAX_UINT32 = 4294967295
    return random.randint(0, MAX_UINT32)

def satoshi_to_btc(satoshi):
    return Decimal(satoshi) / 10**8

def btc_to_satoshi(btc):
    if isinstance(btc, int):
        return btc
    return int(Decimal(btc) * 10**8)

class WebSocket:

    def __init__(self, websockets_path):
        self._websocket_connect = websockets.connect(websockets_path)
        self._websocket = None

        # int id: future
        self._requests = {}

    async def __aenter__(self):
        self._websocket = await self._websocket_connect.__aenter__()
        loop = asyncio.get_event_loop()
        self._task = loop.create_task(self._receive_loop())
        return self

    async def __aexit__(self, *args):
        self._task.cancel()
        await self._websocket_connect.__aexit__(*args)

    async def _receive_loop(self):
        while True:
            message = await self._websocket.recv()
            self._consume(message)

    def _consume(self, message):
        message = json.loads(message)
        # Process the message.
        ident = message["id"]
        future = self._requests[ident]
        del self._requests[ident]
        future.set_result(message)

    async def query(self, command, *params):
        ident = create_random_id()
        future = asyncio.Future()
        self._requests[ident] = future
        request = {
            "command": command,
            "id": ident,
            "params": params
        }
        #print("Sending:", request)
        await self._produce(request)
        response = await future
        assert "id" in response
        assert response["id"] == request["id"]
        assert "result" in response
        ec = response["error"]
        if ec is not None:
            ec = ErrorCode[ec]
        return ec, response["result"]

    async def _produce(self, message):
        message = json.dumps(message)
        await self._websocket.send(message)

    # Used for stop
    async def only_send(self, command):
        request = {
            "command": command,
            "id": create_random_id(),
            "params": []
        }
        await self._produce(request)

class Account:

    @staticmethod
    async def create(ws, name, password, is_testnet=False):
        ec, params = await ws.query("dw_create_account",
                                    name, password, is_testnet)
        if ec:
            assert ec in (ErrorCode.duplicate,)
            return ec
        return None

    @staticmethod
    async def set(ws, name, password):
        ec, params = await ws.query("dw_set_account",
                                    name, password)
        if ec:
            assert ec in (ErrorCode.not_found, ErrorCode.wrong_password)
            return ec
        return None

    @staticmethod
    async def list(ws):
        ec, params = await ws.query("dw_list_accounts")
        assert ec is None
        return params

    @staticmethod
    async def seed(ws):
        ec, params = await ws.query("dw_seed")
        if ec:
            assert ec in (ErrorCode.no_active_account_set,)
            return ec, None
        return None, params

class Pocket:

    @staticmethod
    async def create(ws, name):
        ec, params = await ws.query("dw_create_pocket",
                                    name)
        if ec:
            assert ec in (ErrorCode.no_active_account_set,
                          ErrorCode.duplicate)
            return ec
        return None

    @staticmethod
    async def list(ws):
        ec, params = await ws.query("dw_list_pockets")
        if ec:
            assert ec in (ErrorCode.no_active_account_set,)
            return ec, []
        return None, params[0]

class Wallet:

    @staticmethod
    async def balance(ws, pocket=None):
        ec, params = await ws.query("dw_balance",
                                    pocket)
        if ec:
            assert ec in (ErrorCode.no_active_account_set,
                          ErrorCode.updating_history)
            return ec, None
        return None, satoshi_to_btc(params[0])

    @staticmethod
    async def history(ws, pocket=None):
        ec, params = await ws.query("dw_history",
                                    pocket)
        if ec:
            assert ec in (ErrorCode.no_active_account_set,
                          ErrorCode.updating_history)
            return ec, []
        return None, params

    @staticmethod
    async def send(ws, dests, pocket=None, fee=None):
        dests = [(addr, btc_to_satoshi(amount)) for addr, amount in dests]
        fee = btc_to_satoshi(fee)
        ec, params = await ws.query("dw_send",
                                    dests, pocket, fee)
        if ec:
            assert ec in (ErrorCode.no_active_account_set,
                          ErrorCode.updating_history,
                          ErrorCode.invalid_address,
                          ErrorCode.not_enough_funds)
            return ec, None
        return None, params[0]

    @staticmethod
    async def receive(ws, pocket=None):
        ec, params = await ws.query("dw_receive",
                                    pocket)
        if ec:
            assert ec in (ErrorCode.no_active_account_set,
                          ErrorCode.not_found)
            return ec, []
        return None, params[0]

    @staticmethod
    async def stealth(ws, pocket=None):
        ec, params = await ws.query("dw_stealth",
                                    pocket)
        if ec:
            assert ec in (ErrorCode.no_active_account_set,
                          ErrorCode.not_found)
            return ec, []
        return None, params[0]

class Daemon:

    @staticmethod
    async def validate_address(ws, address):
        ec, params = await ws.query("dw_validate_address",
                                    address)
        assert ec is None
        return params[0]

    @staticmethod
    async def stop(ws):
        await ws.only_send("dw_stop")

