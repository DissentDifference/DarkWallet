import asyncio
import json
import sys
import websockets

import zmq.asyncio
loop = zmq.asyncio.ZMQEventLoop()
asyncio.set_event_loop(loop)

import libbitcoin.server
context = libbitcoin.server.Context()

from darkwallet.wallet_interface import WalletInterface

class Gateway:

    def __init__(self, settings):
        self.settings = settings

        self._wallet = WalletInterface(context, settings)

    async def _accept(self, websocket, path):
        message = await websocket.recv()
        try:
            request = json.loads(message)
        except json.JSONDecodeError:
            print("Error: decoding request", file=sys.stderr)
            return

        # Check request is correctly formed.
        if not self._check(request):
            print("Error: malformed request:", message, file=sys.stderr)
            return

        if request["command"] in self._wallet.commands:
            response = await self._wallet.handle(request)
        else:
            print("Error: unhandled command. Dropping:",
                  message, file=sys.stderr)
            return

        message = json.dumps(response)
        await websocket.send(message)

    def _check(self, request):
        # {
        #   "command": ...
        #   "id": ...
        #   "params": [...]
        # }
        return ("command" in request) and ("id" in request) and \
            ("params" in request and type(request["params"]) == list)

    async def serve(self):
        port = self.settings.port
        return await websockets.serve(self._accept, "localhost", port)

def start_ws(settings):
    gateway = Gateway(settings)

    tasks = [gateway.serve()] + context.tasks()

    asyncio.get_event_loop().run_until_complete(asyncio.wait(tasks))

