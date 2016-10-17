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

    def _check_request(self, request):
        # {
        #   "command": ...
        #   "id": ...
        #   "params": [...]
        # }
        return ("command" in request) and ("id" in request) and \
            ("params" in request and type(request["params"]) == list)

    async def _handle_message(self, message):
        try:
            request = json.loads(message)
        except:
            logging.error("Error decoding message: %s", message, exc_info=True)
            self.close()
            return

        # Check request is correctly formed.
        if not self._check_request(request):
            logging.error("Malformed request: %s", request, exc_info=True)
            self.close()
            return

        response = await self._handle_request(request)
        if response is None:
            self.close()
            return

        self.queue(response)

    async def _handle_request(self, request):
        print("Request", request)
        ec, height = await self._client.last_height()
        if ec:
            print("Error reading block height: %s" % ec)
            return
        response = {
            "id": request["id"],
            "error": None,
            "result": [
                height
            ]
        }
        return response

    def queue(self, message):
        # Calling write_message on the socket is not thread safe
        self._context.spawn(self._send, message)

    def _send(self, message):
        print("Response", message)
        try:
            self.write_message(message)
        except tornado.websocket.WebSocketClosedError:
            logging.warning("Dropping response to closed socket: %s",
                            message, exc_info=True)
        except Exception as e:
            print("Error sending:", str(e))
            traceback.print_exc()
            print("Message:", message.keys())

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

