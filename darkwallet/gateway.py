import json
import random
import tornado.options
import tornado.web
import tornado.websocket

import libbitcoin.server

# Debug stuff
import logging
logging.basicConfig(level=logging.DEBUG)

class QuerySocketHandler(tornado.websocket.WebSocketHandler):
    def initialize(self, context, client, settings):
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

class GatewayApplication(tornado.web.Application):

    def __init__(self, context, settings):
        self._settings = settings

        client_settings = libbitcoin.server.ClientSettings()
        client_settings.query_expire_time = settings.bs_query_expire_time
        client_settings.socks5 = settings.socks5
        self._client = context.Client("tcp://gateway.unsystem.net:9091",
                                      client_settings)

        handlers = [
            (r"/", QuerySocketHandler, dict(
                context=context, client=self._client, settings=settings)),
        ]

        tornado_settings = dict(debug=True)
        tornado_settings.update(tornado.options.options.as_dict())
        super().__init__(handlers, tornado_settings)

    def start_listen(self):
        print("Listening on port %s" % self._settings.port)
        self.listen(self._settings.port)

def start(settings):
    context = libbitcoin.server.TornadoContext()
    app = GatewayApplication(context, settings)
    app.start_listen()
    context.start()

