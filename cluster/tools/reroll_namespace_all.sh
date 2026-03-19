#!/usr/bin/env bash

for i in {1..3}
do
  l="$i: $(lorem -l 5)"
  echo "$l"
  sleep 1
done
