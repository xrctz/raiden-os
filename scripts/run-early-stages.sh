#!/bin/bash
# Helper used during development: runs the stages that do not need the
# Raiden OS packages yet (tools, bootstrap, APT setup, base system).
set -e
B="$(dirname "$(readlink -f "$0")")/build.sh"
for s in host bootstrap aptsetup base; do
  if [ -f /var/tmp/raiden-build/stamps/$s ]; then echo "stage $s already done"; continue; fi
  bash "$B" --only "$s"
done
echo "EARLY STAGES DONE"
