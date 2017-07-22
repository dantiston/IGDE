#!/bin/bash
set -e

python=1
node=2

# Method to run at end
function cleanup {
  echo python
  echo node
  #kill $python
  #kill $node
  echo "Exiting..."
}

# Setup exit command
trap cleanup EXIT

# Start the services
python3 flask