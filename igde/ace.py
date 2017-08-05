"""
lui.py

interface for interacting with ACE in LUI mode
"""

import logging

# For Popen
import termios
import tty
import pty
import os
import sys

from subprocess import Popen, PIPE

from delphin.interfaces.ace import AceParser


class InteractiveAce(AceParser):
    """
    ace -g <grammar> -l --lui-fd=3 --input-from-lui 3<&0 3&>1
    """

    # TODO: Command doesn't run bash, can't use redirects
    #LUI_COMMANDS = ["-l", "--lui-fd=3", "--input-from-lui", "3<&0", "3>&1"]
    LUI_COMMANDS = ["-l", "--lui-fd=3", "--input-from-lui"]

    def __init__(self, grm, cmdargs=None, executable=None, env=None,
                 tsdbinfo=False, **kwargs):
        if cmdargs:
            cmdargs.extend(self.LUI_COMMANDS)
        else:
            cmdargs = list(self.LUI_COMMANDS)
        tsdbinfo = False
        super().__init__(grm, cmdargs, executable, env, tsdbinfo, **kwargs)
        self.receive = self._igde_receive


    def send(self, datum):
        """
        Send *datum* (e.g. a sentence or MRS) to ACE.
        """
        try:
            #self._p.stdin.write("parse {}\f".format(datum))
            #self._p.stdin.flush()
            self._p.communicate("parse {}\f".format(datum))
        except (IOError, OSError):  # ValueError if file was closed manually
            logging.info(
                'Attempted to write to a closed process; attempting to reopen'
            )
            self._open()
            #self._p.stdin.write("parse {}\f".format(datum))
            #self._p.stdin.flush()
            self._p.communicate("parse {}\f".format(datum))


    def _igde_receive(self):
        lines = self._result_lines()
        response, lines = _make_response(lines)
        response['RESULTS'] = [
            dict(zip(('MRS', 'DERIV'), map(str.strip, line.split(' ; '))))
            for line in lines
        ]
        return response


    def _result_lines(self, termini=None):
        poll = self._p.poll
        next_line = self._p.stdout.readline # TODO: This is a PROBLEM

        if termini is None:
            termini = self._termini
        i, end = 0, len(termini)
        cur_terminus = termini[i]

        lines = []
        while i < end:
            s = next_line()
            if s == '' and poll() != None:
                logging.info(
                    'Process closed unexpectedly; attempting to reopen'
                )
                self.close()
                self._open()
                break
            else:
                lines.append(s.rstrip())
                if cur_terminus.search(s):
                    i += 1
        return [line for line in lines if line != '']


    # TODO: This isn't working
    def _open(self):
        old_tty = termios.tcgetattr(sys.stdin)
        tty.setraw(sys.stdin.fileno())
        master_fd, slave_fd = pty.openpty()
        self._p = Popen(
            [self.executable, '-g', self.grm] + self._cmdargs + self.cmdargs,
            stdin=slave_fd,
            stdout=slave_fd,
            env=self.env,
            universal_newlines=True,
            close_fds=False,
            pass_fds=(master_fd, slave_fd)
        )
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_tty)


    def close(self):
        """
        Close the ACE process.
        """
        self._p.stdin.close()
        for line in self._p.stdout:
            logging.debug('ACE cleanup: {}'.format(line.rstrip()))
        self._p.stdout.close()
        retval = self._p.wait()
        return retval
