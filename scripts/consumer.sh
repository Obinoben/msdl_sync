#!/bin/bash

## Init
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
# NTFY
ntfy_queue="msdl_sync_eQgAtgwyvQ85hlum"

consumer_lock=/tmp/ntfy.lock

# Ne lance qu'un seul consumer
flock -n ${consumer_lock} -c "ntfy subscribe ${ntfy_queue} --exec  \"${SCRIPT_DIR}/manager.sh\""

exit 0
