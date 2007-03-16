# keysimul.py
#----------------------------------------------------------------------
# 
"""
    KeySimul - Key Simulator for Series 60

    @copyright: 2007 -  Lee Chee Meng skyleecm@gmail.com
    @License: GPL
"""
#----------------------------------------------------------------------
# test 2 keys input
#----------------------------------------------------------------------

from key_codes import EKeyPageUp, EKeyPageDown
from time import clock


DefaultKeyTimeInterval = 0.8

ModeDef = 0
ModeNum = 1
ModeCaps = 2
ModeToggle = 3  # for num & caps

NoneType = type(None)


class KeySimul:
    def __init__(self, mode=0, keyTimeInterval=DefaultKeyTimeInterval):
        self.mode = mode
        self.keyTimeInterval = keyTimeInterval
        self.lastKey = []

    def key(self, code):
        if self.mode & ModeNum:
            if code >= 0x30 and code <= 0x39:
                return chr(code)
            
        self.appendKey(code)
        c = self.evalKey()
        if c and c.islower():
            if self.mode & ModeCaps:
                return c.upper()
        return c

    def appendKey(self, code):
        self.lastKey.append((code, clock()))

    def evalKey(self):
        c = key2(self.lastKey, self.keyTimeInterval)
        if isinstance(c, (str, unicode, NoneType)):
            return c
        self.mode = self.mode ^ c
        if self.mode == ModeToggle:
            self.mode = c

    def clear(self):
        self.lastKey = []


#----------------------------------------------------------------------
# simple 2 number keys -> alphabet key (a-z)
#   and for punctuation symbols.
#
#   1       2 abc   3 def
#   4 ghi   5 jkl   6 mno
#   7 pqrs  8 tuv   9 wxyz
#   *       0       #
# (1)   (0)     (*)     (#)
# -|/   @$%     .:;     
# [\{   ~ (     `"'     <=
# ]_}   ?&)     ^ ,     >
#  !             *      +#
# 
#----------------------------------------------------------------------
#   1       2       3
#         z(a)     (e)
#           b       m
#   h       l       c
#   4       5       6
#  (i)x   j(s)k    (o)
#   g       f       y
#   p       d       w
#   7       8       9
#  (r)q   v(t)     (n)
#           u
#           0
# eg. 21=z 22=a 25=b 63=c 85=d 33=e ..
#----------------------------------------------------------------------

k2m = {'21': 'z', '22': 'a', '25': 'b', '2#': '2',
       '33': 'e', '36': 'm',            '3#': '3',
       '41': 'h', '44': 'i', '47': 'g', '4#': '4', '45': 'x',
       '54': 'j', '56': 'k', '52': 'l', '5#': '5', '55': 's', '58': 'f',
       '63': 'c', '66': 'o', '69': 'y', '6#': '6',
       '74': 'p', '77': 'r', '78': 'q', '7#': '7',
       '87': 'v', '88': 't', '80': 'u', '8#': '8', '85': 'd',
       '96': 'w', '99': 'n',            '9#': '9',
       '01': '@', '02': '$', '03': '%',
       '04': '~', '05': '', '06': '(',
       '07': '?', '08': '&', '09': ')', '0*': '\t', '00': ' ', '0#': '0',
       '11': '-', '12': '|', '13': '/',
       '14': '[', '15': '\\', '16': '{',
       '17': ']', '18': '_', '19': '}', '1*': '\n', '10': '!', '1#': '1',
       '*1': '.', '*2': ':', '*3': ';',
       '*4': '`', '*5': '"', '*6': "'",
       '*7': '^', '*8': '', '*9': ',', '*0': '*',
       '#4': '<', '#5': '=', '#6': unichr(EKeyPageUp), 
       '#7': '>', '#9': unichr(EKeyPageDown), '#*': '+', '#0': '#',
       '*#': ModeNum, '##': ModeCaps}

def key2(keys, timeLimit):
    num = len(keys)
    if num == 1:
        return
    if num > 2:
        raise Exception("KeySimul bug!?")
    dt = keys[1][1] - keys[0][1]
    if dt > timeLimit:  # ignore both keys?
        c = None
        keys[0:2] = [keys[1]]   # retain 2nd key
    else:
        cs = chr(keys[0][0]) + chr(keys[1][0])
        c = k2m.get(cs, None)
        if c == '': c = None
        keys[0:2] = []
    return c

