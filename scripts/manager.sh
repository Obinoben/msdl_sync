#!/bin/bash

echo $m


for archive in $(echo "$m" | jq -r '.archives'); do
  echo $archive
done
