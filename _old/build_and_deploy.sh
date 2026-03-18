#!/usr/bin/env bash

# This script will assist in doing a build and deploy for vanguard.
# The basic operation is just to present a text based menu of steps to execute, and the user can
# choose one of the steps, press Enter, and it will run that step.
# Although it doesn't automate much, it makes it simple to execute commands with no chance of a typo.
# It remembers your place in the process, so it is less likely to get confused and miss a step or
# perform a step twice.
# After a step completes with a 0 exit status, the next step is automatically selected.
#
# The build steps are defined in one of the STEP_LABELS* arrays. Each entry in these arrays can
# be any of these forms:
#    - Just the command you want to execute
#    - Some friendly text followed by the command string in parantheses
#    - Just some friendly text and put the actual command in the command_map map structure.
#    - A Comment -- anything after a # character
#
# Currently, the script can do a full deploy (the default), or a back-end only deploy if you use
# the -b or --backend-only  command line args.
#
# The only difference between a full deploy and a backend-only deploy is which directory we are
# in when we run the make.sh command.

usage() {
    echo ""
    echo "usage: build_and_deploy.sh [opts]"
    echo "       opts: -h, --help            Show this screen and exit"
    echo "             -b, --backend-only    Use backend-only step list"
    echo ""
    exit 0
}

BACKEND_ONLY=false

PARSED=$(getopt --options hb --longoptions help,backend-only --name "$0" -- "$@")
if [[ $? -ne 0 ]]; then
    usage
fi
eval set -- "$PARSED"
while true; do
    case "$1" in
        -h|--help)         usage ;;
        -b|--backend-only) BACKEND_ONLY=true; shift ;;
        --)                shift; break ;;
        *)                 usage ;;
    esac
done

if [ "$(pwd)" != "/root/vanguard" ]; then
    echo "ERROR: You must be in the /root/vanguard directory to use this script."
    # exit 1
fi

STEP_LABELS_FULL=(
    "git pull"
    "Get build merges (jaguar/tools/cicd/get_build_merges.sh -v | tee /tmp/changes.txt)"
    "git status"
    "git pull"
    "Make (./make.sh current)"
    "git diff # should only see changes to api.json and version files"
    "Commit version changes (git commit -a -m \"rc build\" && git push)"
    "Promote to rc (./promote.sh latest rc)"
    "Deploy to rc (cluster/tools/reroll_namespace_all.sh rc -j 3 --one)"
    "# TEST PRODUCT FUNCTIONALITY ON RC SWIMLANE"
    "Run playwright tests"
    "Promote to prod (./promote.sh latest prod)"
    "Deploy to prod (cluster/tools/reroll_namespace_all.sh prod -j 2 --one)"
    "Promote to dev (./promote.sh latest dev)"
    "Deploy to dev (cluster/tools/reroll_namespace_all.sh dev -j 2 --one)"
    "Promote to staging (./promote.sh latest staging)"
    "Deploy to staging (cluster/tools/reroll_namespace_all.sh staging -j 2 --one)"
    "Rotate all images (rotate-all-images-wrapper.sh)"
    "-- quit --"
)

STEP_LABELS_BACKEND=(
    "git pull"
    "Get build merges (jaguar/tools/cicd/get_build_merges.sh -v | tee /tmp/changes.txt)"
    "git status"
    "git pull"
    "Make (cd jaguar ; ./make.sh current)"
    "git diff # should only see changes to api.json and version files"
    "Commit version changes (git commit -a -m \"rc build\" && git push)"
    "Promote to rc (./promote.sh latest rc)"
    "Deploy to rc (cluster/tools/reroll_namespace_all.sh rc -j 3 --one)"
    "Promote to prod (./promote.sh latest prod)"
    "Deploy to prod (cluster/tools/reroll_namespace_all.sh prod -j 2 --one)"
    "Promote to dev (./promote.sh latest dev)"
    "Deploy to dev (cluster/tools/reroll_namespace_all.sh dev -j 2 --one)"
    "Promote to staging (./promote.sh latest staging)"
    "Deploy to staging (cluster/tools/reroll_namespace_all.sh staging -j 2 --one)"
    "Rotate all images (rotate-all-images-wrapper.sh)"
    "-- quit --"
)

if [[ "$BACKEND_ONLY" == true ]]; then
    STEP_LABELS=("${STEP_LABELS_BACKEND[@]}")
else
    STEP_LABELS=("${STEP_LABELS_FULL[@]}")
fi

selected=0

declare -A command_map=(
    ["Run playwright tests"]='docker run -it --rm --name playwright-headless --ipc=host -v /tmp/.X11-unix:/tmp/.X11-unix -v ~/vanguard:/vanguard mcr.microsoft.com/playwright:v1.56.1-noble /bin/bash -c "cd /vanguard/e2e && npx playwright test --config playwright.all.config.ts -j 5"'
)

get_command() {
    local label="$1"
    if [[ -v "command_map[$label]" ]]; then
        echo "${command_map[$label]}"
    elif [[ "$label" =~ \((.+)\)$ ]]; then
        echo "${BASH_REMATCH[1]}"
    else
        echo "$label"
    fi
}

draw_menu() {
    clear
    if [[ "$BACKEND_ONLY" == true ]]; then
        echo "[ BACKEND ONLY ]  Use ↑ and ↓ to move, ENTER to select:"
    else
        echo "[ FULL DEPLOY ] Use ↑ and ↓ to move, ENTER to select:"
    fi
    echo
    for i in "${!STEP_LABELS[@]}"; do
        if [[ $i == $selected ]]; then
            printf "\e[7m  %s\e[0m\n" "${STEP_LABELS[$i]}"
        else
            printf "  %s\n" "${STEP_LABELS[$i]}"
        fi
    done
}

get_selection() {
    while true; do
        draw_menu
        IFS= read -rsn1 key
        if [[ $key == $'\x1b' ]]; then
            read -rsn2 key
            case $key in
                '[A') ((selected--)) ;;
                '[B') ((selected++)) ;;
            esac
        elif [[ $key == "" ]]; then
            break
        fi
        ((selected < 0)) && selected=$(( ${#STEP_LABELS[@]} - 1 ))
        ((selected >= ${#STEP_LABELS[@]})) && selected=0
    done
    clear
}

while true; do
    get_selection

    LABEL="${STEP_LABELS[$selected]}"

    if [[ "$LABEL" == "-- quit --" ]]; then
        echo "Exiting."
        exit 0
    fi

    if [[ "$LABEL" == \#* ]]; then
        continue
    fi

    COMMAND=$(get_command "$LABEL")

    echo ">>> Running: $COMMAND"
    echo "----------------------------------------"
    eval "$COMMAND"
    EXIT_CODE=$?
    echo "----------------------------------------"

    if [[ $EXIT_CODE -ne 0 ]]; then
        echo "⚠️  Step exited with code $EXIT_CODE. Press any key to return to menu..."
        read -rsn1
    else
        (( selected++ ))
        while [[ $selected -lt ${#STEP_LABELS[@]} ]] &&
              [[ "${STEP_LABELS[$selected]}" == \#* ]]; do
            (( selected++ ))
        done
        echo "✓ Step complete. Press any key to continue to next step..."
        read -rsn1
    fi
done
