#!/usr/bin/env bash

source cluster/tools/confirm_cluster.sh

confirm_cluster

for i in {1..3}
do
    l="$i : $(base64 /dev/urandom 2> /dev/null | head -c 60)"
    echo $l
    sleep 1
done

while true; do
    read -p "About to reroll by namespace, do you wish to continue? (y/n) " yn
    case $yn in
        [Yy]* ) break;;  # If the user enters "y" or "Y", break the loop and continue with the script
        [Nn]* ) exit;;   # If the user enters "n" or "N", exit the script
        * ) echo "Please answer yes (y) or no (n).";;  # If the user enters anything else, prompt them again
    esac
done

