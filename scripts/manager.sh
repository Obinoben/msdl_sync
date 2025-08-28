#!/bin/bash

echo $m


for archive in $(echo "$m" | jq -r '.archives' | sed 's/,//g'); do

  echo $archive
done
