import json
import random
import tornado.web
import tornado.websocket

import libbitcoin.server

# Debug stuff
import logging
logging.basicConfig(level=logging.DEBUG)

class QuerySocketHandler(tornado.websocket.WebSocketHandler):
    def initialize(self, context, client):
        self._context = context
        self._client = client

    def on_message(self, message):
        self._context.spawn(self._handle_message, message)

    async def _handle_message(self, message):
        print(message)
        ec, height = await self._client.last_height()
        if ec:
            print("Error reading block height: %s" % ec)
            return
        result = {
            "id": 1,
            "error": None,
            "result": [
                height
            ]
        }
        self.write_message(json.dumps(result))

def make_app(context):
    client = context.Client("tcp://gateway.unsystem.net:9091")
    return tornado.web.Application([
        (r"/", QuerySocketHandler, dict(context=context, client=client)),
    ])

def start(settings):
    context = libbitcoin.server.TornadoContext()
    app = make_app(context)
    app.listen(8888)
    context.start()

