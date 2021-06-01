#!/usr/bin/env bash

function create_wallet {
  curl -X POST \
    http://10.200.0.7:9090/wallet \
    -H 'cache-control: no-cache' \
    -H 'content-type: application/json' \
    -H 'postman-token: 6141e831-6df0-411c-e382-1631384e6861' \
    -d '{
    "method": "create_account",
    "params": {
        "name": "Greg"
    },
    "jsonrpc": "2.0",
    "id": 1
}'
}

export create_wallet