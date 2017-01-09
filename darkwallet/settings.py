import argparse
import configparser
import os.path

import darkwallet.util

def get_default_config_path():
    return os.path.join(os.path.expanduser("~"), ".darkwallet")

class Settings:

    def load(self):
        args = self._parse()
        self._load(args)

    def _parse(self):
        # Command line arguments
        parser = argparse.ArgumentParser(prog="darkwallet-daemon")
        parser.add_argument("--version", "-v", action="version",
                            version="%(prog)s 2.0")
        parser.add_argument("--config", "-c", dest="config",
                            help="Change default config path.",
                            default=get_default_config_path())
        parser.add_argument("--port", "-p", dest="port",
                            help="Run on the given port.",
                            default=None)
        parser.add_argument("--tornado", "-t", dest="use_tornado",
                            action="store_const", const=True, default=False,
                            help="Use the Tornado implementation instead.")
        return parser.parse_args()

    def _load(self, args):
        self.use_tornado_impl = args.use_tornado

        self.config_path = args.config
        darkwallet.util.make_sure_dir_exists(self.config_path)
        self.config_filename = os.path.join(self.config_path, "darkwallet.cfg")
        darkwallet.util.make_sure_file_exists(self.config_filename)

        config = configparser.ConfigParser()
        config.read(self.config_filename)

        # [main]
        main = config["main"]
        # Give precedence to command line over config file.
        self.port = args.port
        if self.port is None:
            self.port = int(main.get("port", 8888))

        # [wallet]
        wallet = config["wallet"]
        self.gap_limit = int(wallet.get("gap-limit", 5))
        self.master_pocket_name = wallet.get("master-pocket-name", "master")

        # [bs]
        bs = config["blockchain-server"]
        self.url = bs.get("url", "tcp://gateway.unsystem.net:9091")
        self.testnet_url = bs.get("testnet-url",
            "tcp://testnet.unsystem.net:9091")
        self.query_expire_time = float(bs.get("query-expire-time", 4.0))
        self.socks5 = bs.get("socks5", None)

    def save(self):
        config = configparser.ConfigParser()
        config["main"] = {
            "port": self.port
        }
        config["wallet"] = {
            "gap-limit": self.gap_limit,
            "master-pocket-name": self.master_pocket_name
        }
        config["blockchain-server"] = {
            "url": self.url,
            "testnet-url": self.testnet_url,
            "query-expire-time": self.query_expire_time
        }
        if self.socks5:
            config["blockchain-server"]["socks5"] = self.socks5
        with open(self.config_filename, "w") as configfile:
            config.write(configfile)

