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
        return parser.parse_args()

    def _load(self, args):
        self.config_path = args.config
        darkwallet.util.make_sure_dir_exists(self.config_path)
        config_filename = os.path.join(self.config_path, "darkwallet.cfg")
        darkwallet.util.make_sure_file_exists(config_filename)

        config = configparser.ConfigParser()
        config.read(config_filename)

        # [main]
        main = config["main"]
        # Give precedence to command line over config file.
        self.port = args.port
        if self.port is None:
            self.port = int(main.get("port", 8888))

        # [wallet]
        wallet = config["wallet"]
        self.gap_limit = int(wallet.get("gap_limit", 5))
        self.master_pocket_name = wallet.get("master-pocket-name", "master")

        # [bs]
        bs = config["blockchain-server"]
        self.bs_url = bs.get("url", "tcp://gateway.unsystem.net:9091")
        self.bs_query_expire_time = int(bs.get("query-expire-time", 200))
        self.socks5 = bs.get("socks5", None)

