import logging
import darkwallet.jsonchan
import darkwallet.ticker

from darkwallet.lib.crypto2crypto import CryptoTransportLayer

class LegacyModule:

    commands = [
        # Ticker
        "fetch_ticker",
        # JSON Chan
        "chan_post",
        "chan_list",
        "chan_get",
        "chan_subscribe",
        "chan_unsubscribe",
        "disconnect_client"
    ]

    def __init__(self, settings):
        self._p2p = CryptoTransportLayer(
            settings.p2p_port, settings.external_ip, settings.internal_ip)
        self._p2p.join_network(settings.seeds)
        self._json_chan_handler = darkwallet.jsonchan.JsonChanHandler(self._p2p)
        self._ticker_handler = darkwallet.ticker.TickerHandler()

    def handle_request(self, socket, request):
        if self._json_chan_handler.handle_request(socket, request):
            return
        #if self._brc_handler.handle_request(socket, request):
        #    return
        if self._ticker_handler.handle_request(socket, request):
            return
        logging.warning("Unhandled command. Dropping request: %s",
            request, exc_info=True)

