#!/usr/bin/env bash


for i in {1..2}
do
    l="$i : $(base64 /dev/urandom 2> /dev/null | head -c 60)"
    echo $l
    sleep 1
done

echo "Oops, something went wrong!"


exit 1

