#!/usr/bin/env bash

MY_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)


# Confirm this is te CLUSTER and the NAMESPACE the user is wanting to perform actions in
# Use this as an entry point for almost any cluster operation
confirm_cluster() {
    local answer
    local cluster
    cluster=$(kubectl config current-context)
    echo "Target Cluster/Namespace/DockerTag"
    echo "--"
    echo "Cluster  :  ${cluster}"
    echo "Namespace:  ${NS}"
    echo "Tag      :  ${TAG}"
    echo "Host     :  ${HOST}"
    echo "--"
    while true; do
        read -p "Proceed with this cluster/namespace (y/n) " answer
        answer=$(echo "$answer" | tr '[:upper:]' '[:lower:]') # Convert to lowercase

        case "$answer" in
            y|yes)
                return 0 ;; # Return success (0) if the answer is yes
            n|no)
                exit 1 ;; #exit the whole thing
            *)
                echo "Please answer y or n." ;; # Ask again if the input is not y/n
        esac
    done
}

