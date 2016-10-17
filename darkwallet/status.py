import json
import tornado.web

class StatusHandler(tornado.web.RequestHandler):
    def __init__(self, *args, **kwargs):
        tornado.web.RequestHandler.__init__(self, *args)
        self.app = kwargs['app']
    def get(self):
        stats = {
            'brc': { 'peers': self.app.brc_handler._brc.last_nodes, 'issues': self.app.brc_handler._brc.issues },
            'radar': { 'peers': self.app.brc_handler._radar.radar_hosts, 'issues': self.app.brc_handler._radar.issues },
            'ticker': {'issues': self.app.ticker_handler._ticker.issues, 'price': self.app.ticker_handler._ticker.ticker.get('EUR', {}).get('24h_avg', 'error')},
            'p2p': {'peers': len(self.app.p2p._peers.keys())}
        }
        self.write(json.dumps(stats))


