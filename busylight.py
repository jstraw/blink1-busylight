import cmd
import readline
import time
import subprocess
import sys

import transitions

class busyrgb(object):
    """
    Helper class to allow color tuples to have names.
    """
    available = (0,255,0)
    wfh = (255,0,255)
    busy = (255,0,0)

    meeting = (200,200,200)
    deploy =  (255,105,180)
    work = (255,0,255)
    ooo = (255,0,0)
    interruptable = (0,255,0)


class leftmanager(object):
    """
    Manager of the "left" LED in the blink1, not using subclasses.

    States:
        "available": Available for someone to walk up
        "wfh": Working from home, check other LED for tasking state
        "busy": Please don't disturb me, I'm working here.
    Transitions:
        'break' or 'available': switch to available states
        'wfh': switch to the work from home states
        'work', 'dnd', 'busy': switch to the working states
    """
    states = [
        transitions.State(name='available', on_enter=['become_available']),
        transitions.State(name='wfh', on_enter=['become_wfh']),
        transitions.State(name='busy', on_enter=['become_busy'])
    ]
    transitions = [
        ['break', ['wfh', 'busy'], 'available'],
        ['available', ['wfh', 'busy'], 'available'],
        ['wfh', ['available', 'busy'], 'wfh'],
        ['work', 'available', 'busy'],
        ['dnd', 'available', 'busy'],
        ['busy', 'available', 'busy']
    ]

    def __init__(self, light):
        """
        Initialize the "left" LED in the blink1

        :param light object: an instance of busylight to control the led switch
        """
        self.light = light
        self.colors = busyrgb()
        self.machine = transitions.Machine(model=self, states=self.states,
            transitions=self.transitions, initial='available')
        self.become_available()

    def become_available(self):
        """Callback to change to Available"""
        self.light.left('slow', self.colors.available)

    def become_busy(self):
        """Callback to change to Busy"""
        self.light.left('fast', self.colors.busy)

    def become_wfh(self):
        """Callback to change to work from home"""
        self.light.left('slow', self.colors.wfh)



class rightmanager(object):
    """
    Manager of the "right" LED in the blink1, not using subclasses.

    States:
        "meeting": In a meeting
        "deploy": Doing a deploy
        "work": I'm working on a task
        "ooo": I'm on PTO/OOO today
        "interruptable": Feel free to say hi
    Transitions:
        'meet': go to a in_meeting
        'deploy': start a deploy
        'ooo': out of the office
        'work': busy time
        'bored': Come talk
    """
    states = [
        transitions.State(name='meeting', on_enter=['in_meeting']),
        transitions.State(name='deploy', on_enter=['doing_deploy']),
        transitions.State(name='work', on_enter=['doing_work']),
        transitions.State(name='ooo', on_enter=['im_out']),
        transitions.State(name='interruptable', on_enter=['im_bored'])
    ]
    transitions = [
        ['meet', ['deploy', 'ooo', 'work', 'interruptable'], 'meeting'],
        ['deploy', ['meeting', 'ooo', 'work', 'interruptable'], 'deploy'],
        ['ooo', ['meeting', 'deploy', 'work', 'interruptable'], 'ooo'],
        ['work', ['meeting', 'deploy', 'ooo', 'interruptable'], 'work'],
        ['bored', ['meeting', 'deploy', 'ooo', 'work'], 'interruptable']
    ]
    def __init__(self, light):
        """
        Initialize the "right" LED in the blink1

        :param light object: an instance of busylight to control the led switch
        """
        self.light = light
        self.colors = busyrgb()
        self.machine = transitions.Machine(model=self, states=self.states,
            transitions=self.transitions, initial='interruptable')
        self.im_bored()

    def in_meeting(self):
        self.light.right('fast', self.colors.meeting)

    def doing_deploy(self):
        self.light.right('fast', self.colors.deploy)

    def doing_work(self):
        self.light.right('fast', self.colors.deploy)

    def im_bored(self):
        self.light.right('fast', self.colors.interruptable)

    def im_out(self):
        self.light.right('slow', self.colors.ooo)
        self.lm.busy()

class busylight(cmd.Cmd):
    """
    Build the controller for the blink1, and manage the state controllers
    """
    left_led = 1
    right_led = 2
    colors = busyrgb()
    speeds = {'slow': 10000, 'fast': 1000}
    # cmd object keys
    completekey = "\t"
    prompt = 'status > '

    def __init__(self, cmd=False, left=1, right=2):
        """
        :param left int: Which led is on the left
        :param right int: Which led is on the right
        """
        self.left_led = left
        self.right_led = right
        self.__set_light__(self.speeds['fast'], (255,0,0))
        time.sleep(1)
        self.__set_light__(self.speeds['fast'], (0,255,0))
        time.sleep(1)
        self.__set_light__(self.speeds['fast'], (0,0,255))
        self.lstate = leftmanager(self)
        self.rstate = rightmanager(self)
        self.lstate.rm = self.rstate
        self.rstate.lm = self.lstate
        super().__init__()
        if cmd:
            self.cmdloop()

    def __set_light__(self, speed, color, led=0):
        try:
            s = self.speeds[speed]
        except KeyError:

            s = speed
        subprocess.check_call(['/usr/local/bin/blink1-tool', '--rgb', ','.join(str(x) for x in color), '-m', str(s), '-l', str(led)], stdout=subprocess.PIPE)

    def right(self, speed, color):
        self.__set_light__(speed, color, self.right_led)

    def left(self, speed, color):
        self.__set_light__(speed, color, self.left_led)

    def postcmd(self, stop, line):
        self.do_showtransitions(line)

    def do_off(self, line):
        self.__set_light__(100, (0,0,0), 0)
        print('\n')
        sys.exit(0)
    do_EOF=do_off
    do_exit=do_off

    def get_transitions(self):
        s = self.lstate.machine.get_triggers(self.lstate.state) + \
                self.rstate.machine.get_triggers(self.rstate.state)
        return [x for x in s if not x.startswith('to')]

    def completenames(self, text, *ignored):
        x = super().completenames(text, ignored)
        y = [i for i in self.get_transitions() if i.startswith(text)]
        return x + y

    def completetransitions(self, text, line, begidx, endidx):
        return [i for i in self.get_transitions() if i.startswith(text)]

    def default(self, line):
        if line in self.get_transitions():
            if line in self.lstate.machine.get_triggers(self.lstate.state):
                getattr(self.lstate, line)()
            else:
                getattr(self.rstate, line)()

    def do_showtransitions(self, line):
        print('Available Transitions')
        print('Availablity (' + self.lstate.state + '): ' + ', '.join( \
                x for x in self.lstate.machine.get_triggers(self.lstate.state) \
                if not x.startswith('to')))
        print('Tasking (' + self.rstate.state + '): ' + ', '.join( \
                x for x in self.rstate.machine.get_triggers(self.rstate.state) \
                if not x.startswith('to')))

    def do_state(self, line):
        print("Current States:\n Availablility: %s\n Tasking: %s" % (self.lstate.state, self.rstate.state))

if __name__ == '__main__':
    b = busylight(cmd=True)
