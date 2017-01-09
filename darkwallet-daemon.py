#!/usr/bin/python3
import sys

import darkwallet

def main():
    # Load config file settings
    settings = darkwallet.Settings()
    settings.load()

    # Start the darkwallet-daemon
    if settings.use_tornado_impl:
        darkwallet.start(settings)
    else:
        darkwallet.start_ws(settings)
    return 0

if __name__ == "__main__":
    sys.exit(main())

