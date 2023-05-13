#!/bin/sh -
# This assumes the repo is cloned to a home directory that has a config
# subdirectory and this script is run with
# ./copy-to-config.sh
if [ -d ../config/custom_components ]; then
  mkdir ../config/custom_components/vantage 2> /dev/null
  cp custom_components/vantage/* ../config/custom_components/vantage
else
  echo "Directory ../config/custom_components does not exist"
fi

