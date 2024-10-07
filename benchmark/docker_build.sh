#!/bin/bash
CMD_BASE="$(readlink -f "$0" 2>/dev/null || greadlink -f "$0")" || CMD_BASE="$0"; CMD_BASE="$(dirname "$CMD_BASE")"

set -e
cp -a "$CMD_BASE"/../vendor "$CMD_BASE"/ && \
docker build \
       --file benchmark/Dockerfile \
       -t aider-benchmark \
       .
