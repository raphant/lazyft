#!/usr/bin/env bash

# Sync lazyft_pkg to remote server. Delete files that are not in the source
# Remote dir = sage-server1.local:/home/sage/ftworkdir/lazyft_pkg
rsync ./lft_rest sage@sage-server1.local:/home/sage/ftworkdir --archive --verbose --compress --ignore-existing --delete --recursive
