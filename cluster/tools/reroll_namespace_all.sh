#!/usr/bin/env bash

for i in {1..3}
do
    r=$(base64 /dev/urandom 2> /dev/null | head -c 60)
    l="$i: $r"
    echo "$l"
    sleep 1
done
