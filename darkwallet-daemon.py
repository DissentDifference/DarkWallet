#!/usr/bin/python3
import sys

import darkwallet

def main():
    # Load config file settings
    settings = darkwallet.Settings()
    settings.load()

    # Start the darkwallet-daemon
    if settings.use_ws_impl:
        darkwallet.start_ws(settings)
    else:
        darkwallet.start(settings)
    return 0

if __name__ == "__main__":
    sys.exit(main())

