#!/bin/sh -
# This assumes the repo is cloned to the config directory
# and this script is run from the directory containing it.
# ./copy-to-config.sh
if [ -d ../custom_components ]; then
  mkdir ../custom_components/vantage 2> /dev/null
  cp custom_components/vantage/* ../custom_components/vantage
else
  echo "Directory ../custom_components does not exist"
fi

