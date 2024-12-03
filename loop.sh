#!/bin/bash

REMOTE="a6000:/root/tmpl-benchmark-app/results"
LOCAL_DIR="results/remote"
INTERVAL=0.1

while true; do
    rclone copy "$REMOTE" "$LOCAL_DIR" --ignore-existing --progress --transfers=8 --include "*.jpg"
    sleep "$INTERVAL"
done
