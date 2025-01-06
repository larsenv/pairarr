#!/bin/bash

# This script is used when running the app through docker. It handles scheduling the script

# Default interval is 300 seconds (5 minutes) if not set
INTERVAL=${SCRIPT_INTERVAL:-300}

while true; do
    if ps aux | grep "[p]airarr.py" > /dev/null; then
        echo "Pairarr is already running. Exiting..."
    else
        python -u /app/pairarr.py
    fi

    dt=$(date '+%d/%m/%Y %H:%M:%S');
    echo "$dt - Waiting for $INTERVAL seconds before checking again..."
    sleep $INTERVAL
done
