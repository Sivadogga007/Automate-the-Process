#!/bin/sh
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)" || exit 1
sh ./start.sh "$@"
status=$?
printf '\nPress Enter to close this window.'
read -r answer
exit "$status"
