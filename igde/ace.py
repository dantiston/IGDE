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
    #LUI_COMMANDS = ["-l", "--lui-fd=3", "--input-from-lui"]
    #LUI_COMMANDS = ["ace", "-l", "--lui-fd=3", "--input-from-lui", "3<&0", "3>&1"]
    #LUI_COMMANDS = "-l --lui-fd={fd} --input-from-lui {fd}<&0 {fd}>&1"
    LUI_COMMAND = "\"ace -g {grammar} -l --lui-fd={fd} --input-from-lui {fd}<&0 {fd}>&1\""


    def __init__(self, grm, cmdargs=None, executable=None, env=None,
                 tsdbinfo=False, **kwargs):
        #if cmdargs:
        #    cmdargs.extend(self.LUI_COMMANDS)
        #else:
        #    cmdargs = list(self.LUI_COMMANDS)
        tsdbinfo = False
        #executable = 'bash'
        super().__init__(grm, cmdargs, executable, env, tsdbinfo, **kwargs)
        self.receive = self._igde_receive


    def _igde_receive(self):
        lines = self._result_lines()
        response, lines = _make_response(lines)
        response['RESULTS'] = [
            dict(zip(('MRS', 'DERIV'), map(str.strip, line.split(' ; '))))
            for line in lines
        ]
        return response


    # TODO: This isn't working
    def _open(self):
        #fd = os.fdopen(3)
        #print(fd)

        in_fd, out_fd = os.pipe()

        #print(" ".join([self.executable, '-g', self.grm, self.LUI_COMMANDS.format(fd=in_fd)]))
        print(self.LUI_COMMAND.format(fd=in_fd, grammar=self.grm))
        self._p = Popen(
            #" ".join([self.executable, '-g', self.grm] + self._cmdargs + self.cmdargs),
            #" ".join([self.executable, '-g', self.grm, self.LUI_COMMANDS.format(fd=in_fd)]),
            self.LUI_COMMAND.format(fd=in_fd, grammar=self.grm),
            #stdin=PIPE,
            #stdout=PIPE,
            #stdin=3,
            #stdout=3,
            stdin=in_fd,
            stdout=in_fd,
            env=self.env,
            #close_fds=False,
            shell=True,
            pass_fds=[in_fd, out_fd]
        )

#        old_tty = termios.tcgetattr(sys.stdin)
#        tty.setraw(sys.stdin.fileno())
#        master_fd, slave_fd = pty.openpty()
#        self._p = Popen(
#           [self.executable, '-g', self.grm] + self._cmdargs + self.cmdargs,
#           stdin=slave_fd,
#           stdout=slave_fd,
#           env=self.env,
#           universal_newlines=True,
#           close_fds=False,
#           pass_fds=(master_fd, slave_fd)
#        )
#        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_tty)


#     def close(self):
#         """
#         Close the ACE process.
#         """
#         self._p.stdin.close()
#         for line in self._p.stdout:
#             logging.debug('ACE cleanup: {}'.format(line.rstrip()))
#         self._p.stdout.close()
#         retval = self._p.wait()
#         return retval
