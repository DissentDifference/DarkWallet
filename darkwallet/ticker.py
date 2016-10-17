import logging
import threading
import json
import time
import urllib.error
from urllib.request import urlopen

class Ticker(threading.Thread):

    daemon = True

    def __init__(self):
        super(Ticker, self).__init__()
        self.lock = threading.Lock()
        self.ticker = {}
        self.start()
        self.issues = 0

    def run(self):
        while True:
            self.pull_prices()
            time.sleep(5 * 60)

    def pull_prices(self):
        ticker_all = self.query_ticker()
        if not ticker_all:
            return
        with self.lock:
            for currency, ticker_values in ticker_all.items():
                self.ticker[currency] = ticker_values

    def query_ticker(self):
        url = "https://api.bitcoinaverage.com/ticker/global/all"
        try:
            f = urlopen(url)
        except urllib.error.HTTPError:
            self.issues = 1
            return
            self.issues = 1
        except urllib.error.URLError:
            return
        self.issues = 0
        return json.loads(f.read().decode("ascii"))

    def fetch(self, currency):
        with self.lock:
            try:
                return self.ticker[currency]
            except KeyError:
                return None

class TickerHandler:

    def __init__(self):
        self._ticker = Ticker()

    def handle_request(self, socket_handler, request):
        if request["command"] != "fetch_ticker":
            return False
        if not request["params"]:
            logging.error("No param for ticker specified.")
            return True
        currency = request["params"][0]
        ticker_value = self._ticker.fetch(currency)
        response = {
            "id": request["id"],
            "error": None,
            "result": [ticker_value]
        }
        socket_handler.queue(response)
        return True

