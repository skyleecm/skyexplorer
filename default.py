# default.py
#----------------------------------------------------------------------
# 
"""
    Sky Explorer - File explorer for Series 60

    @copyright: 2007 -  Lee Chee Meng skyleecm@gmail.com
    @License: GPL
"""

import os, appuifw

#----------------------------------------------------------------------
# 1.0.1 changes
# get the correct private dir for S60 3rd Edition
#----------------------------------------------------------------------

def appDir():
    appuifw.note(u"Starting Sky Explorer", u"info")
    (dir, name) = os.path.split(appuifw.app.full_name())
    import e32
    if e32.s60_version_info >= (3,0):
        sep = os.sep
        uid = appuifw.app.uid().lower()
        appPath = os.path.join('private', uid)
        import sys
        for p in sys.path:
            if os.path.splitdrive(p)[1][1:].lower() == appPath:
                dir = p
                break            
    #sys.path.append(dir)
    return dir

dir = appDir()
try:
    import explorer
    explorer.run(dir)
except Exception, e:
    appuifw.note(unicode(e), u"info")

