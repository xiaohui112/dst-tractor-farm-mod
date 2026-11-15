#!/bin/zsh
cd -- "$(dirname "$0")"
exec /Library/Developer/CommandLineTools/usr/bin/python3 server.py --open
