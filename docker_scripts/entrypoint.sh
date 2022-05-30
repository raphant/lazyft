#!/bin/sh
# Read in the file of environment settings
. .env
#printenv
# Then run the CMD
exec "$@"
