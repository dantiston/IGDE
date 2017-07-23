# IGDE
Integrated Grammar Development Environment: A online web interface for the high performance [ACE](http://sweaglesw.org/linguistics/ace/) parser for working with [DELPH-IN](http://www.delph-in.net) style [HPSG](https://en.wikipedia.org/wiki/Head-driven_phrase_structure_grammar) natural language grammars, including parsing, generating, and exploring grammars (viewing lexical entries & rules, interactive unification, etc.).

Processing with ACE is handled through [PyDelphin](https://github.com/goodmami/pydelphin).

# VERSION HISTORY
v0.3: significantly restructuring app, removing django, foundation, and socket.io, adding flask

v0.2: core functionality, parsing to derivation trees and MRS tables. Moved model HTML code from PyDelphin to models.py

v0.1: basic UI, parsing.


# RUNNING IGDE
*NOTE: This section is under construction while the IGDE is under initial development.*
To run a development instance of the IGDE, make sure to follow the directions to set up the IGDE below. Then, in two separate terminals, run:

```
cd igde
bash run.sh
```

# DEPLOYING IGDE
Coming... sometime!

# SETUP
*NOTE: The IGDE is developed alongside [PyDelphin](https://github.com/goodmami/pydelphin), both of which are written in Python3. Make sure to use Python3 specific commands when appropriate.*

```
# Download and install IGDE
git clone https://github.com/dantiston/IGDE.git
cd IGDE/igde
bash install.sh
```

The current version of the IGDE relies on a static ACE-compiled grammar image. I recommend to store this at `~/delphin/erg.dat`. You can compile your own grammar image with ACE or download a pre-compiled image. More info from the [ACE website](http://sweaglesw.org/linguistics/ace/).
