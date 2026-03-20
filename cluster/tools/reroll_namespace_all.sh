#!/usr/bin/env bash

for i in {1..3}
do
    l="$i : $(base64 /dev/urandom | head -c 60)"
    echo "$l"
    sleep 1
done
