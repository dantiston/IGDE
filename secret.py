import os
import sys
import json

# Make the key
key = str(os.urandom(24))


# Get filename from arguments
target = 'idge.json'
if len(sys.argv) > 1:
    target = sys.argv[1]

# Create the file if needed
if not os.path.isfile("igde.json"):
    open("igde.json", 'w').close()

# Store the key in the file
with open("igde.json", 'r+') as f:
    try:
        j = json.load(f)
    except json.decoder.JSONDecodeError:
        j = {}

    j['key'] = key
    f.seek(0)
    json.dump(j, f, sort_keys=True, indent=4, separators=(',', ': '))
