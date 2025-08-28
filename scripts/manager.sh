#!/bin/bash

read input
msg=$(echo "$input" | jq -r '.message')
echo "Message reçu dans mon_script.sh: $msg"
