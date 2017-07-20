#!/bin/bash
set -e

# Method to run at end
function cleanup {
  python=$1
  node=$2
  kill $python
  kill $node
  echo "Exiting..."
}

# Setup exit command
trap cleanup EXIT

# Start the services
