import cmd
import readline

import transitions

import blink1

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
    leftstates = [
        transitions.State(name='available', on_enter=['become_available']),
        transitions.State(name='wfh', on_enter=['become_wfh']),
        transitions.State(name='busy', on_enter=['become_busy'])
    ]
    lefttransitions = [
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
        'out', 'ooo': out of the office
        'work': busy time
        'bored': Come talk
    """
    rightstates = [
        transitions.State(name='meeting', on_enter=['in_meeting']),
        transitions.State(name='deploy', on_enter=['doing_deploy']),
        transitions.State(name='work', on_enter=['doing_work']),
        transitions.State(name='ooo', on_enter=['out']),
        transitions.State(name='interruptable', on_enter=['im_bored'])
    ]
    righttransitions = [
        ['meet', ['deploy', 'ooo', 'work', 'interruptable'], 'meeting'],
        ['deploy', ['meet', 'ooo', 'work', 'interruptable'], 'deploy'],
        ['out', ['meet', 'deploy', 'work', 'interruptable'], 'ooo'],
        ['ooo', ['meet', 'deploy', 'work', 'interruptable'], 'ooo'],
        ['work', ['meet', 'deploy', 'ooo', 'interruptable'], 'work'],
        ['bored', ['meet', 'deploy', 'ooo', 'work'], 'interruptable']
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

    def in_meeting(self):
        self.light.right('fast', self.colors.meeting)

    def doin_deploy(self):
        self.light.right('fast', self.colors.deploy)

    def doin_work(self):
        self.light.right('fast', self.colors.deploy)

    def im_bored(self):
        self.light.right('fast', self.colors.interruptable)

    def out(self):
        self.light.right('slow', self.colors.ooo)

class busylight(cmd.Cmd):
    """
    Build the controller for the blink1, and manage the state controllers
    """
    left = 1
    right = 2
    colors = busyrgb()
    speeds = {'slow': 10000, 'fast': 1000}
    def __init__(self, left=1, right=2):
        """
        :param left int: Which led is on the left
        :param right int: Which led is on the right
        """
        self.left = left
        self.right = right
        self.light = blink1.blink1()
        self.light.fade_to_color(speeds['fast'], (255,0,0))
        time.sleep(1)
        self.light.fade_to_color(speeds['fast'], (0,255,0))
        time.sleep(1)
        self.light.fade_to_color(speeds['fast'], (0,0,255))
        self.lstate = leftmanager(self)
        self.rstate = rightmanager(self)
        super(cmd.Cmd, self).__init__()

    def __set_light__(self, speed, color, led):
        try:
            s = self.speeds[speed]
        except KeyError:

            s = speed
        self.light.fade_to_color(s, color, led)

    def right(self, speed, color):
        self.__set_light__(speed, color, self.right)

    def left(self, speed, color):
        self.__set_light__(speed, color, self.left)

    def get_transitions(self):
        return self.lstate.get_triggers(self.lstate.state) + \
            self.rstate.get_triggers(self.rstate.state)

    def completedefault(self, text, line, begidx, endidx):
        return [i for i in self.get_transitions() if i.startswith(text)]

    def default(self, line):
        if line in self.get_transitions():
            if line in self.lstate.get_triggers(self.lstate.state):
                getattr(self.lstate, line)()
            else:
                getattr(self.rstate, line)()
