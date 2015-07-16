# IGDE
Integrated Grammar Development Environment: A online web interface for the high performance [ACE](http://sweaglesw.org/linguistics/ace/) parser for working with [DELPH-IN](http://www.delph-in.net) style [HPSG](https://en.wikipedia.org/wiki/Head-driven_phrase_structure_grammar) natural language grammars, including parsing, generating, and exploring grammars (viewing lexical entries & rules, interactive unification, etc.).

The IGDE is built with [Django](https://www.djangoproject.com), combining Django's templating system with the responsive web design tools of [Foundation](http://foundation.zurb.com) using the [Django-zurb-foundation app](https://pypi.python.org/pypi/django-zurb-foundation/5.0.2). The system uses a live server-client connection through [Socket.io](http://socket.io) to interact with ACE on the client and processes the requests on the server.

Processing with ACE is handled through [PyDelphin](https://github.com/goodmami/pydelphin).

# VERSION HISTORY
v0.2: core functionality, parsing to derivation trees and MRS tables. Moved model HTML code from PyDelphin to models.py

v0.1: basic UI, parsing.


# RUNNING IGDE
*NOTE: This section is under construction while the IGDE is under initial development.*
To run a development instance of the IGDE, make sure to follow the directions to set up the IGDE below. Then, in two separate terminals, run:

```
cd IGDE/nodejs
nodejs igde.js
```

```
cd IGDE
python manage.py runserver localhost:3000
```

# DEPLOYING IGDE
Coming... sometime!

# SETUP
*NOTE: The IGDE is developed alongside [PyDelphin](https://github.com/goodmami/pydelphin), both of which are written in Python3. Make sure to use Python3 specific commands when appropriate.*
To set up IGDE, you'll need several different packages and types of packages. A comprehensive list (Much of this from [here](http://www.maxburstein.com/blog/realtime-django-using-nodejs-and-socketio/)):

```
#https://docs.djangoproject.com/en/dev/topics/install/
sudo apt-get install python3-pip
sudo pip3 install django
 
#https://github.com/joyent/node/wiki/Installing-Node.js-via-package-manager
sudo apt-get install python-software-properties
sudo add-apt-repository ppa:chris-lea/node.js
sudo apt-get update
sudo apt-get install nodejs

sudo pip3 install django-zurb-foundation

# Download and install IGDE and pydelphin
git clone https://github.com/dantiston/pydelphin.git
git clone https://github.com/dantiston/IGDE.git

# Install pydelphin
cd pydelphin
sudo python setup.py install
```

The current version of the IGDE relies on a static ACE-compiled grammar image. I recommend to store this at `~/delphin/erg.dat`. You can compile your own grammar image with ACE or download a pre-compiled image. More info from the [ACE website](http://sweaglesw.org/linguistics/ace/).
