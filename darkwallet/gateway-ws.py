import asyncio
import json
import libbitcoin.server
import websockets
import zmq.asyncio

import darkwallet.bs_module
import darkwallet.subscribe_module
import darkwallet.brc
import darkwallet.legacy

class Gateway:

    def __init__(self, context, settings, loop):
        self._context = context
        self._settings = settings
        client_settings = libbitcoin.server.ClientSettings()
        client_settings.query_expire_time = settings.bs_query_expire_time
        self._client = self._context.Client(settings.bs_url, client_settings)
        # Setup the modules
        self._bs_module = darkwallet.bs_module.BitcoinServerModule(self._client)
        #self._subscribe_module = darkwallet.subscribe_module.SubscribeModule(
        #    self._client, loop)
        #self._brc_module = darkwallet.brc.Broadcaster(context, settings, loop,
        #                                          self._client)
        #self._legacy_module = darkwallet.legacy.LegacyModule(settings)

    def _check_request(self, request):
        # {
        #   "command": ...
        #   "id": ...
        #   "params": [...]
        # }
        return ("command" in request) and ("id" in request) and \
            ("params" in request and type(request["params"]) == list)

    async def serve(self, websocket, path):
        success = True
        while success:
            message = await websocket.recv()
            success = await self.process(websocket, message)
            print("resp", len(json.dumps(success)))
            await websocket.send(json.dumps(success))

    async def process(self, websocket, message):
        try:
            request = json.loads(message)
        except:
            logging.error("Error decoding message: %s", message, exc_info=True)
            return False

        # Check request is correctly formed.
        if not self._check_request(request):
            logging.error("Malformed request: %s", request, exc_info=True)
            return False

        #if request["command"] in self._legacy_module.commands:
        #    self._legacy_module.handle_request(self, request)
        #    return False

        response = await self._handle_request(request)
        if response is None:
            print("response is None")
            return False

        print("queueing response")
        await self.send(websocket, response)
        return response
        return True

    async def _handle_request(self, request):
        if request["command"] in self._bs_module.commands:
            response = await self._bs_module.handle(request)
            print("Response returned!")
        #elif request["command"] in self._subscribe_module.commands:
        #    response = await self._subscribe_module.handle(request, self)
        #elif request["command"] in self._brc_module.commands:
        #    response = await self._brc_module.handle(request, self)
        else:
            logging.warning("Unhandled command. Dropping request: %s",
                request, exc_info=True)
            return None
        return response

    async def send(self, websocket, message):
        print("writing %s bytes" % len(json.dumps(message)))
        #await websocket.send(json.dumps(message))

def start(settings):
    loop = zmq.asyncio.ZMQEventLoop()
    asyncio.set_event_loop(loop)
    context = libbitcoin.server.Context()
    darkwallet = Gateway(context, settings, loop)
    tasks = [
        websockets.serve(darkwallet.serve, 'localhost', 8888)
    ]
    tasks.extend(context.tasks())
    loop.run_until_complete(asyncio.wait(tasks))
    loop.close()

