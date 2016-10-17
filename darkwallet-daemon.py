#!/usr/bin/python3
import sys

import darkwallet

def main():
    # Load config file settings
    settings = darkwallet.Settings()
    settings.load()

    # Start the darkwallet-daemon
    darkwallet.start(settings)
    return 0

if __name__ == "__main__":
    sys.exit(main())

