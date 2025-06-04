#!/bin/sh
# filepath: /home/c/si/redes/tp2/tests-public/hub-and-spoke/tmux.sh
set -eu

exe="python ../../router.py"

# Test if files exist first
if [ ! -f "hub.txt" ]; then
    echo "hub.txt not found in $(pwd)"
    exit 1
fi

if [ ! -f "spoke.txt" ]; then
    echo "spoke.txt not found in $(pwd)"
    exit 1
fi

# Keep shell open after command with 'exec bash'
tmux split-pane -v "cd $(pwd) && $exe 127.0.1.10 4 hub.txt; exec bash"

for i in $(seq 1 5) ; do
    tmux split-pane -v "cd $(pwd) && $exe 127.0.1.$i 4 spoke.txt; exec bash"
    tmux select-layout even-vertical
done