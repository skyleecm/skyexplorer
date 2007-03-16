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

def appDir():
    appuifw.note(u"Starting Sky Explorer", u"info")
    (dir, name) = os.path.split(appuifw.app.full_name())
    #sys.path.append(dir)
    return dir

dir = appDir()
import explorer
explorer.run(dir)
