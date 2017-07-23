#########
# secret.py
# Creating and loading local secret for session storage
#########

import os
import json

# No dot when installing...
from constants import Constants as constants

target = constants.igde_json

def init():

    import sys

    # Make the key
    key = str(os.urandom(24))

    # Create the file if needed
    if not os.path.isfile(target):
        open(target, 'w').close()

    # Load the key from the file
    with open(target, 'r+') as f:
        try:
            data = json.load(f)
        except json.decoder.JSONDecodeError:
            data = {}

    data[constants.secret_key] = key

    with open(target, 'w') as f:
        json.dump(data, f, sort_keys=True, indent=4, separators=(',', ': '))


def load():

    if not os.path.isfile(target):
        init()

    with open(target, 'r') as f:
        data = json.load(f)
        return bytes(data[constants.secret_key], 'utf-8')

if __name__ == "__main__":
    init()

