# explorer.py
#----------------------------------------------------------------------
# 
"""
    Sky Explorer - File explorer for Series 60

    @copyright: 2007 -  Lee Chee Meng skyleecm@gmail.com
    @License: GPL
"""

import appuifw
import e32
import sysinfo
import messaging
import keycapture
import graphics
import socket
import re
import os
from os import path
import codecs
import time
from time import localtime, strftime
import zipfile
from sets import Set
from key_codes import EKeyLeftArrow, EKeyRightArrow, EKeyBackspace, EKeyPageUp, EKeyPageDown, EKeyYes, EKeyLeftSoftkey, EKeyRightSoftkey

import keysimul
from dir_util import copy_tree, remove_tree, copy_file, findFiles, zip_tree, unzipDir, mkpath, CopyStopError, filter, path_join, unicode_list

#----------------------------------------------------------------------
# python bugs
#
# double-style listbox (icon) - icons will not change after set_list ,
#   and will crash if an item index > initial number of items
# strftime("%d%b %y", localtime(val)) - %y gives wrong value
#----------------------------------------------------------------------
# bluetooth testing:
# send to PC win2000 BlueSoleil 1.6.1.4
#   it works only after I use OBEX Commander to connect with phone first
#----------------------------------------------------------------------
# 1.0.1 changes
# add Explorer.findApps1 (require applist.pyd - allow S60 3rd Edition)
# add AppItem._pname (same as old AppItem.name - the app filename without ext)
#   the AppItem.name is initialize with app caption (from findApps1)
# fix checklayout
#----------------------------------------------------------------------
# 1.0.2 changes
# fix signal & battery bars disappear using ao_sleep in run.
#----------------------------------------------------------------------
# 1.0.3 changes
# unicode path should be encoded in utf8 when using S60 os functions
#  modify path.join - return in utf8
# support unicode filename, search
#  dir_util.findFiles - support unicode names, return in unicode
#  searchText - support utf_16 files
# !? unicode filename is encoded in utf8 when added to zip file
# unzip in S60 seems to work :)
#  (unzip in other OS may retain the utf8 encoded name)
# support UCS2 sms
# explorertag.py - key, value in Tags are saved in utf8
#----------------------------------------------------------------------

if path.join is not path_join:
    path.join = path_join

TypeANY = 0
TypeDRIVE = 2
TypeFOLDER = 4

CUT = 1
COPY = 2
COPYDRIVE = 3
PASTE = 4
SCREENSHOT = 5

IconFile = u"explorer.mbm"
AppTitle = u"File Explorer"
AboutApp = u"Sky eXplorer v1.0.1 by\nskyleecm@gmail.com\nFor user guide, go to\nhttp://timelesssky.com\nat url\n/blog/sky-explorer"
DefaultName = u"My Phone"
ATxtNew = u"[New]"

EmptyDisplay = u" * EMPTY * <- Go back"
Es = u""

ListStyle = ('Single', 'Double')
ListStrMaxWidth = 25    # ? how to determine
ListAttrMaxWidth = 8

AppRun  = "Z:\\system\\programs\\apprun.exe"
AppsDir = "\\system\\Apps"
AppExt = ".app"
ExeExt = ".exe"
AppMgr = "AppMngr"
# midlets
MidpDir = "\\system\\MIDlets"
MidpExt = ".jar"

ExtClss = ["App"]

ListScrollPg = 6    # number of Listbox items to scroll per page
TextScrollPg = 9    # number of Text lines to scroll per page

#----------------------------------------------------------------------
# menu
MenuFile = [u"File", (u"Search", u"New Folder", u"Rename", u"Delete", u"Properties", u"Tag It")]
MenuEdit = [u"Edit", (u"Cut", u"Copy", u"Paste", u"Select All", u"Invert Selection", u"Select/Unselect")]
MenuTool = [u"Tools", (u"", u"Screenshot", u"Own Screenshot")] #MenuArch
MenuArch = [u"Archive", (u"Add to", u"Extract files")]
MenuView = [u"View", (u"by Name", u"by Type", u"by Size", u"by Date")]
MenuSend = [u"Send", (u"Files by Bluetooth", u"Files by Email", u"Files by MMS", u"SMS")]
MenuSets = [u"Settings"]
MenuAbout = [u"About"]
# menu for atxt
MenuATxt = [u"File", (u"New", u"Open", u"Save", u"Save As", u"Close")]


class AppItem(object):
    def __init__(self, namepath, getEntry):
        self.name, self.p, self.tags = namepath[0], namepath[1], None
        self._appitem = [getEntry(self), getEntry(self, 1)]
        self._pname = path.split(path.splitext(namepath[1])[0])[1].lower()
    def getAppitem(self, iCheck=0): return self._appitem[iCheck]

class AppInterface(object):
    def getAppitem(self, iCheck=0): pass
    def getListContents(self): pass
    def selectPath(self, dir): pass
    def selectItem(self, item): pass

class AppTagItem(AppInterface):
    def __init__(self, app, tagpath):
        self.app, self.tagpath = app, tagpath
        self._appitem = [app.getTagEntry(self.name), app.getTagEntry(self.name, 1)]
    def __eq__(self, other):
        return isinstance(other, AppTagItem) and self.app is other.app and self.tagpath == other.tagpath
    def __ne__(self, other): return not self.__eq__(other)
    def __hash__(self): return hash((AppTagItem, self.app, self.tagpath))   # for dict ops
    def basename(self):
        return path.basename(self.tagpath)
    name = property(basename)

    def getAppitem(self, iCheck=0): return self._appitem[iCheck]
    def getListContents(self):
        return self.app.getTagContents(self.tagpath)
    def selectItem(self, item):
        return self.app.selectItem(item)
        
class App(AppInterface):
    def __init__(self, exp):
        self.name = u"Apps"
        self.exp = exp
        getListboxEntry = self.getListboxEntry
        self.apps = [AppItem(app, getListboxEntry) for app in exp.findApps1()]
        icon = exp.icons[TypeFOLDER]
        self._appitem = exp.listStyle and (self.name, Es, icon) or (self.name, icon)
        self._appmenu = None
        self._stdTags()
        self._readTags()

    def getAppitem(self, iCheck=0): return self._appitem

    def getAppsitems(self):
        exp = self.exp
        return [a.getAppitem(exp.isChecked(a)) for a in self.apps]
    
    def getListContents(self):
        exp = self.exp
        items, apps, name = [], [], self.name
        utags, stags = self._utagsets.keys(), self._tagsets.keys()
        utags.sort()
        stags.sort()
        utags.extend(stags)
        for tag in utags:
            a = AppTagItem(self, os.sep.join([name, tag]))
            items.append(a.getAppitem(exp.isChecked(a)))
            apps.append(a)
        return items + self.getAppsitems(), apps + self.apps

    def getSubTags(self, tags, aset):
        tset = self._utagsets
        return [tag for tag in tset.keys() if (tag not in tags) and (tset[tag] & aset)]
                
    def getTagContents(self, tagpath):
        exp = self.exp
        tags = self._tags(tagpath)
        sset, tset = self._tagsets, self._utagsets
        aset = reduce(lambda x, y: x&y, [tag in sset and sset[tag] or tset[tag] for tag in tags])
        if tags[0] not in sset:
            subtags = self.getSubTags(tags, aset)
            subtags.sort()
            tagitems = [AppTagItem(self, os.sep.join([tagpath, tag])) for tag in subtags]
            apps = self._sortbyName(aset)
            tagitems.extend(apps)
        else:   # no subtag for drive tags
            tagitems = aset
        items, apps = [], []
        for a in tagitems:
            items.append(a.getAppitem(exp.isChecked(a)))
            apps.append(a)
        return items, apps
        
    def getListboxEntry(self, item, iCheck=0):
        exp, name = self.exp, item.name
        #icon = exp.getIcon('', item, p=item.p)
        icon = exp.icons[TypeANY + iCheck]
        if exp.listStyle:
            return (name, Es, icon)
        else:
            return (name, icon)

    def getTagEntry(self, tag, iCheck=0):
        exp = self.exp
        icon = exp.icons[TypeFOLDER + iCheck]
        if exp.listStyle:
            return (tag, Es, icon)
        else:
            return (tag, icon)

    def selectPath(self, dir):
        if dir == self.name:
            return self
        tags = self._tags(dir)
        if tags[0] not in self._tagsets and tags[0] not in self._utagsets:
            raise Exception("%s not found." % dir)
        for tag in tags[1:]:
            if tag not in self._utagsets:
                raise Exception("%s not found." % dir)
        return AppTagItem(self, dir)
    
    def selectItem(self, item):
        if isinstance(item, AppTagItem):
            return item
        try:
            ext = path.splitext(item.p)[1].lower()
            if ext == AppExt:
                e32.start_exe(AppRun, item.p)
            elif ext == ExeExt:
                e32.start_exe(item.p, '')
            elif ext == MidpExt:
                alert("The program does not know how to run %s" % item.name)
                #e32.start_exe(AppRun, item.p)
        except Exception, e:
            alert(e)

    def tagItem(self, item, newtags):
        otags, ntags = Set(item.tags), Set(newtags)
        remtags = otags - ntags
        addtags = ntags - otags
        if not (remtags or addtags):
            return
        aset = self._utagsets
        for tag in remtags:
            if tag in aset:
                aset[tag].remove(item)
        for tag in addtags:
            if tag in aset:
                aset[tag].add(item)
            else:
                aset[tag] = Set([item])
        item.tags = newtags
        self._writeTags()

    def _tags(self, tagpath):
        h = splithead(tagpath)
        i = len(h)
        sep = tagpath[i]
        tags = tagpath[i+1:].split(sep)
        return tags
    
    def _stdTags(self):
        appmgr = AppMgr.lower()
        mgr = None
        aset = dict([(d, Set()) for d in self.exp.e32drives])
        m = {}
        for a in self.apps:
            aset[a.p[0:2]].add(a)
            m[a._pname] = a #m[a.name] = a
            if a._pname == appmgr:
                mgr = a
        for d in aset.keys():
            if not aset[d]:
                del aset[d]
        self._tagsets = aset
        self._mapapps = m
        self._mgr = mgr

    def _userTags(self, pathtags):
        name, m, aset = self.name, self._mapapps, {}
        for p, tags in pathtags.iteritems():
            if not p.startswith(name):
                continue
            names = self._tags(p)
            names[0] = names[0].lower()
            if len(names) > 1 or names[0] not in m:
                continue
            a = m[names[0]]
            a.tags = tags = [tag.strip() for tag in tags.split(',')]
            for tag in tags:
                if tag in aset:
                    aset[tag].add(a)
                else:
                    aset[tag] = Set([a])
        self._utagsets = aset

    def _get_pathtags(self):
        aset = self._utagsets
        m = dict([(aname, []) for aname in self._mapapps.iterkeys()])
        for tag, tset in aset.iteritems():
            for a in tset:
                m[a._pname].append(tag) #m[a.name].append(tag)
        return m
                 
    def _readTags(self):
        try:
            from explorertag import Tags
            # in 1.0.3, key, value in Tags are saved in utf8
            tags = dict([(unicode(k, 'utf8'), unicode(v, 'utf8')) for k, v in Tags.iteritems()])
            self._userTags(tags)
        except Exception, e:
            if not isinstance(e, ImportError):
                error(e)
            self._utagsets = {}

    def _writeTags(self):
        name = self.name
        pathtags = self._get_pathtags()
        m = dict([(os.sep.join([name, aname]), ','.join(tags)) for aname, tags in pathtags.iteritems() if tags])
        p = path.join(self.exp.appDir, 'explorertag.py')
        writeText(p, _str_tags(m))

    def _sortbyName(self, aset):
        alist = [(a.name, a) for a in aset]
        alist.sort()
        return [a for name, a in alist]

    def _uninstall(self, item):
        try:    # only run manager
            if e32.s60_version_info >= (3,0):
                e32.start_exe(self._mgr.p, '')
            else:
                e32.start_exe(AppRun, self._mgr.p) #item.p
        except Exception, e:
            alert(e)
        
    def uninstall(self):
        if self._mgr is None:
            alert("Cannot find application manager.")
            return
        names = self.exp.getSelectedNames()
        for a in names:
            if isinstance(a, AppItem):
                self._uninstall(a)
                break   # its manual
        self.exp.refresh()
                
    def setMenus(self):
        if self._appmenu:
            return self._appmenu
        menu = self.exp.allMenu
        txt, filemenus = menu[0]
        editmenu, toolmenu, sendmenu = menu[1], menu[2], menu[4]
        # Search, Uninstall, Tag It
        filemenu = (txt, (filemenus[0], (u"Uninstall", self.uninstall), filemenus[-1]))
        editmenu = (editmenu[0], editmenu[1][3:])   # sel ..
        toolmenu = (toolmenu[0], toolmenu[1][2:])   # screenshot
        sendmenu = (sendmenu[0], sendmenu[1][3:])   # sms
        self._appmenu = [filemenu, editmenu, toolmenu, sendmenu]
        self._appmenu.extend(menu[5:])
        return self._appmenu

class SearchList(AppInterface):
    "A subset of app list."
    def __init__(self, app, sublist, exp):
        self.app, self.sublist, self.exp = app, sublist, exp
    def getAppitem(self, iCheck=0): return self.app.getAppitem(iCheck)
    def getListContents(self):
        exp = self.exp
        return [a.getAppitem(exp.isChecked(a)) for a in self.sublist], self.sublist
    def selectPath(self, dir): pass # not use
    def selectItem(self, item): return (item is None) and self.app or self.app.selectItem(item)
    # special case of returning self.app if not selecting a child


class Explorer(object):
    def __init__(self, appDir):
        self.appDir = appDir
        self.currDir = ''
        self.listStyle = 0
        self.listViewExtra = 1  # view 1 more attribute in single-style listbox
        self.viewAttr = {"Type": viewType, "Size": viewSize, "Date": viewDate}
        self.appIcon = unicode(path.join(appDir, IconFile))
        self.keymod = keysimul.KeySimul()
        self._drives = None
        self._exts = {}
        self.readPref()
        checklayout()

    def readPref(self):
        pref, timezone = None, 0
        try:
            from explorerpref import Prefs
            pref = dict(Prefs)
            timezone = int(pref['timezone']) * -3600
        except Exception, e:
            if pref:
                pref['timezone'] = '0'
            else:
                pref = {'email': "", 'smtpHost': "", 'timezone': '0', 'textmode': '',
                    'texteditExt': '', 'imageDir': "E:\\images"}
        if not hasattr(time, 'timezone'):
            time.timezone = timezone
        for opt in ['textmode', 'texteditExt', 'imageDir']:
            if opt not in pref:
                pref[opt] = ''
        self.pref = pref
        self.setTexteditExts(pref['texteditExt'])

    def writePref(self):
        p = path.join(self.appDir, 'explorerpref.py')
        writeText(p, _str_pref(self.pref))

    def initPref(self):
        pref = self.pref
        prefs = [u"email", u"smtpHost"]
        fds = [(name.capitalize(), 'text', unicode(pref.get(name, ''))) for name in prefs]
        timezone = int(pref['timezone'])
        tz = (u"Timezone (eg. 8)", 'number', timezone)
        choice = [u"Normal", u"2 keys"]
        txtmode = (u"Text enter mode", 'combo', (choice, pref['textmode'] and 1 or 0))
        editext = (u"File exts-TextEditor(eg. py txt)", 'text', unicode(pref['texteditExt']))
        imagedir = (u"Images directory", 'text', unicode(pref['imageDir']))
        fds.extend([tz, txtmode, editext, imagedir])
        f = appuifw.Form(fds, appuifw.FFormEditModeOnly | appuifw.FFormDoubleSpaced)
        f.save_hook = self.setPref
        return f

    def setPref(self, fds):
        pref = self.pref
        prefs = ["email", "smtpHost", "timezone"]
        for i in [0, 1]: pref[prefs[i]] = fds[i][2]
        timezone = fds[2][2]
        if timezone != int(pref['timezone']):
            time.timezone = timezone * -3600
            pref['timezone'] = str(timezone)
        mode = fds[3][2][1] and '2' or ''
        self.setTextMode(mode)
        self.setTexteditExts(fds[4][2])
        self.setImageDir(fds[5][2])
        self.writePref()
        return True

    def setTextMode(self, mode=''):
        self.pref['textmode'] = mode
        self.keyc.forwarding = mode == '' and 1 or 0

    def setTexteditExts(self, exts):
        self.pref['texteditExt'] = exts
        extlist = (',' in exts) and exts.lower().split(',') or exts.lower().split()
        self._editExts = dict([(ext.strip(), 1) for ext in extlist])

    def setImageDir(self, p):
        mkpath(p, 0777)
        self.pref['imageDir'] = p
        
    def getApp(self): return self._exts[u"Apps"]
    
    def addExtension(self, o):
        self._exts[o.name] = o

    def addExtToDrives(self):
        if self._exts:
            exts = self._exts.keys()
            exts.sort()
            exts = [self._exts[ex] for ex in exts]
            self.e32drives.extend(exts)
            self._drives.extend([o.getAppitem() for o in exts])

    def initExts(self):
        md = alert.func_globals
        for clsname in ExtClss:
            if clsname in md:
                self.addExtension(md[clsname](self))
                
    def findApps(self):
        jext = "*" + MidpExt
        apps = []
        for d in self.e32drives:
            appdir = d + AppsDir
            if not path.exists(appdir):
                continue
            folders, files = listdir(appdir)
            for dir in folders:
                if dir[0] == '[':
                    continue
                a = dir + AppExt
                p = path.join(appdir, dir, a)
                if path.exists(p):
                    apps.append((dir, p))
            appdir = d + MidpDir
            if not path.exists(appdir):
                continue
            folders, files = listdir(appdir)
            for dir in folders:
                p = path.join(appdir, dir)
                files = filter([unicode(name, 'utf8') for name in os.listdir(p)], jext)
                if files and len(files) == 1:
                    apps.append((files[0], path.join(p, files[0])))
        apps.sort()
        return apps

    def findApps1(self):
        try:
            import applist
        except Exception, e:
            alert(e)
            return self.findApps()
        apps = [(ai[1].strip() and ai[1] or path.split(path.splitext(ai[2])[0])[1], ai[2])
            for ai in applist.applist()]
        apps.sort()
        return apps
    
    def getDrives(self):
        if self._drives is None:
            self._drives = [self.getListboxEntry('', d) for d in self.e32drives]
            self.addExtToDrives()
        if not self.currSels: return self._drives
        num = len(self._drives) - len(self._exts)
        items = [self.getListboxEntry('', d) for d in self.e32drives[0:num]]
        items.extend(self._drives[num:])
        return items
    drives = property(getDrives)

    def getEmptyItem(self): return self.emptyItems[self.listStyle]
    emptyItem = property(getEmptyItem)

    def getKeyHandler(self, k): return lambda: self.onKey(k)

    def getMenuHandler(self, menu, item=None):
        if menu == "View" or menu == "Send":
            menu = lcase(menu)
        else:
            menu = "on"
        i = item.find('/')
        if i > 0:
            item = ''.join(item.split('/'))
        return getattr(self, (menu + item).replace(' ', ''))

    def setRootMenu(self, bInsearch=False):
        if bInsearch:
            if self._rootsrchmenu: return self._rootsrchmenu
        elif self._rootmenu:
            return self._rootmenu
        menu = self.allMenu
        txt, filemenus = menu[0]
        editmenu, toolmenu, viewmenu, sendmenu = menu[1], menu[2], menu[3], menu[4]
        if bInsearch:
            # Search, Rename, Delete, Properties
            filemenu = (txt, filemenus[0:1] + filemenus[2:-1])
            editmenu = (editmenu[0], editmenu[1][0:2] + editmenu[1][3:])    # no paste
            toolmenu = (toolmenu[0], toolmenu[1][0:1] + toolmenu[1][2:])     # no extract
            m = self._rootsrchmenu = [filemenu, editmenu, toolmenu, viewmenu, sendmenu]
        else:
            # Search, Properties
            filemenu = (txt, (filemenus[0], filemenus[-2]))
            editmenu = (editmenu[0], editmenu[1][1:2] + editmenu[1][3:])   # copy, sel ..
            toolmenu = (toolmenu[0], toolmenu[1][2:])   # screenshot
            sendmenu = (sendmenu[0], sendmenu[1][3:])   # sms
            m = self._rootmenu = [filemenu, editmenu, toolmenu, sendmenu]
        m.extend(menu[5:])
        return m

    def setFolderMenu(self):
        if self._dirmenu:
            return self._dirmenu
        menu = self.allMenu
        filemenu = menu[0]
        # remove Tag It
        filemenu = (filemenu[0], filemenu[1][0:-1])
        self._dirmenu = menu[1:]
        self._dirmenu.insert(0, filemenu)
        return self._dirmenu
    
    def changeMenu(self):
        menu = appuifw.app.menu
        if isinstance(self.searchFs, AppInterface):
            head = splithead(self.currDir)
            if head in self._exts:
                menu = self._exts[head].setMenus()
        elif self.currDir:
            menu = self.setFolderMenu()
        else:
            if self.searchFs and isinstance(self.searchFs, list):
                menu = self.setRootMenu(True)
            else:
                menu = self.setRootMenu()
        if menu is not appuifw.app.menu:
            appuifw.app.menu = menu
        
    def initMenu(self):
        menus = [MenuFile, MenuEdit, MenuTool, MenuArch, MenuView, MenuSend]
        menu = [(m[0], [ [item, self.getMenuHandler(m[0], item)]
                              for item in m[1] if item] ) for m in menus]
        archMenu = menu.pop(3)
        # Note: doesn't allow sub-submenu!?
        #archMenu = (archMenu[0], tuple([tuple(t) for t in archMenu[1] ]))
        #menu[2][1].insert(0, archMenu)  # in Tools
        archMenu[1][0][0], archMenu[1][1][0] = u"Add to Archive", u"Extract Archive files"
        menu[2][1][0:0] = archMenu[1]
        menu += [(MenuSets[0], self.settings), (MenuAbout[0], self.about)]
        delMenu = menu[0][1][3]
        delMenu[0] = delMenu[0] + " [C]"
        selMenu = menu[1][1][-1]
        selMenu[0] = selMenu[0] + " [00]"
        sshotMenu = menu[2][1][2]
        sshotMenu[0] = sshotMenu[0] + " [Dial]" # EKeyYes
        for i in range(0, len(menu) - 2):
            menu[i] = (menu[i][0], tuple([tuple(t) for t in menu[i][1] ]))
        self.viewby = "Name"
        return menu

    def initText(self):
        self.atxt = appuifw.Text()
        self.atxtFile = ""
        menu = [(m[0], tuple([ (item, self.getMenuHandler(m[0], item))
                              for item in m[1] ]) ) for m in [MenuATxt]]
        menu += [(MenuSend[0], self.onSend)]
        self.atxtMenu = menu
        ckeys = "0123456789*#"
        self.keyc = keyc = keycapture.KeyCapturer(self.onTextKey)
        keyc.keys = [ord(k) for k in ckeys]
        # without forwarding, other apps cannot work!?
        keyc.forwarding = self.pref['textmode'] == '' and 1 or 0
        # for menu key capture (screenshot)
        self.keyc_ss = keyc = keycapture.KeyCapturer(self.onScreenshotKey)
        keyc.keys = [EKeyLeftSoftkey, EKeyRightSoftkey]
        keyc.forwarding = 1
        
    def initApp(self):
        import string
        self.createIcons()
        self.emptyItems = ([(EmptyDisplay, self.icons[TypeANY])],
                           [(EmptyDisplay, Es, self.icons[TypeANY])])
        self.e32drives = e32.drive_list()
        #self.drivesList = ([(d, self.icons[TypeDRIVE]) for d in self.e32drives],
        #               [(d, Es, self.icons[TypeDRIVE]) for d in self.e32drives])
        self.cbAction = self.searchFs = None
        self.currSels = {}
        self.initExts()
        self.currItems = self.drives
        self.currNames = self.e32drives
        self.lb = appuifw.Listbox(self.drives, self.onSelect)
        self.lb.bind(EKeyLeftArrow, self.onKeyLeft)
        self.lb.bind(EKeyRightArrow, self.onKeyRight)
        self.lb.bind(EKeyBackspace, self.onDelete) 
        self.lb.bind(EKeyYes, self.onScreenshot)
        ckeys = string.digits + string.ascii_letters + '#'
        for k in ckeys:
            self.lb.bind(ord(k), self.getKeyHandler(k))
        #
        self.initText()
        self._rootmenu = self._rootsrchmenu = self._dirmenu = None
        self.allMenu = self.initMenu()
        appuifw.app.title = AppTitle
        # 1 tab doesn't get displayed
        appuifw.app.set_tabs([DefaultName], self.onTab)
        self.changeMenu()
        appuifw.app.exit_key_handler = self.onExit
        appuifw.app.focus = self.onFocus
        appuifw.app.body = self.lb
        
    def exitApp(self):
        self.keyc.stop()
        self.keyc_ss.stop()
        appuifw.app.exit_key_handler = appuifw.app.focus = None
        self.currItems = self.emptyItems = None
        self.icons = None
        self.uiLock.signal()
        
    def run(self):
        self.uiLock = e32.Ao_lock()
        oldTitle = appuifw.app.title
        self.initApp()

        self.uiLock.wait()
        appuifw.app.set_tabs([], None)
        appuifw.app.title = oldTitle
        appuifw.app.menu = []
        appuifw.app.body = None
        self.lb = None
        self.icons = None
        appuifw.app.set_exit()

    def showEditorPath(self):
        appuifw.app.title = unicode(self.atxtFile, 'utf8') or ATxtNew
        
    def showPathname(self):
        appuifw.app.title = unicode(self.currDir, 'utf8') or AppTitle

    def refresh(self):
        self.display(self.getSelectedItemName())
        
    def display(self, childName=None):
        self.showPathname()
        self.setListboxContents(self.searchFs or self.currDir,
                                childName, self.viewby)
        
    def setListboxContents(self, dir, selectItem=None, viewby=None):
        if isinstance(dir, list):   # search list
            if viewby:
                dir = listtuplefiles(dir, viewby)
            if dir and isinstance(dir[0][0], tuple):
                items = [self.getListboxEntryA(fd, attr) for fd, attr in dir]
                files = [fn[0] for fn in dir]
            else:
                items = [self.getListboxEntryA(fd) for fd in dir]
                files = dir
        elif isinstance(dir, AppInterface):   # app
            items, files = dir.getListContents()
        elif dir:
            folders, files = listdir(dir, viewby)
            folders.extend(files)
            sfiles = folders
            if sfiles and isinstance(sfiles[0], tuple):
                items = [self.getListboxEntry2(dir, fn) for fn in sfiles]
                files = [fn[0] for fn in sfiles]
            else:
                items = [self.getListboxEntry(dir, fn) for fn in sfiles]
                files = sfiles
        else:
            items, files = self.drives, self.e32drives
        # Listbox does not allow 0 item!
        if not items:
            items, files = self.emptyItem, [EmptyDisplay]
        self.currItems = items
        self.currNames = files
        if selectItem:
            try:
                selectIndex = files.index(selectItem)
                self.lb.set_list(items, selectIndex)
                return
            except ValueError, e:   # can happen for app
                pass
        self.lb.set_list(items)
            
    def getListboxEntry(self, dir, name):
        if dir:
            icon = self.getIcon(dir, name)
        else:
            icon = self.getDriveIcon(name)
        if self.listStyle:
            return (name, Es, icon)
        else:
            return (name, icon)

    def getListboxEntry2(self, dir, tname):
        icon = self.getIcon(dir, tname[0])
        if self.listStyle:
            return (tname[0], tname[1], icon)
        elif self.listViewExtra:
            return (self.getListItemName(tname[0], tname[1]), icon)
        else:
            return (tname[0], icon)

    def getListboxEntryA(self, name, attr=None):    # for search list
        icon = self.getIcon('', name)
        if self.listStyle:
            if attr is None: attr = name[1]
            return (name[0], attr, icon)
        elif self.listViewExtra and attr is not None:
            return (self.getListItemName(name[0], attr), icon)
        else:
            return ("%s [%s]" % (name[0], name[1]), icon)

    def getListItemName(self, name, attr):
        """experimental: attr will not align properly!
           put attr val on the left"""
        v = self.viewAttr[self.viewby]
        val = v(attr)[0:ListAttrMaxWidth]
        #nlen = ListStrMaxWidth - len(val) - 1
        return val + '  ' + name #name + val

    def getIcon(self, dir, name, p=None):
        if p is None:
            p = pathjoin(dir, name)
        chk = self.currSels.get(name, 0)
        if path.isdir(p):
            return self.icons[TypeFOLDER + chk]
        else:
            return self.icons[TypeANY + chk]

    def getDriveIcon(self, name):
        chk = self.currSels.get(name, 0)
        return self.icons[TypeDRIVE + chk]
        
    def createIcons(self):
        num = (TypeFOLDER + 2) * 2
        self.icons = [appuifw.Icon(self.appIcon, i, i+1) for i in range(0, num, 2)]
        
    def selectDir(self, dir, childName=None):
        self.currDir = dir
        self.currSels = {}
        self.searchFs = None
        self.viewby = "Name"
        self.changeMenu()
        self.display(childName)
        
    def selectFile(self, fname):
        ext = getType(fname)
        if ext in self._editExts:
            self.editText(fname, self.atxtMenu[0:1])
            return
        if type(fname) is not unicode:
            fname = unicode(fname, 'utf8')
        try:
            if ext == AppExt[1:]:
                e32.start_exe(AppRun, fname)
            elif ext == ExeExt[1:]:
                e32.start_exe(fname, '')
            else:
                appuifw.Content_handler().open_standalone(fname)
        except Exception, e:
            alert(e)

    def selectApp(self, item, fs=None):
        o = item
        if fs:
            o = fs.selectItem(item)
        if not o: return
        self.searchFs = o
        if not (item is None and isinstance(fs, SearchList)):
            self.currDir = path.join(self.currDir, o.name)
        self.currSels = {}
        self.changeMenu()
        self.display()

    def selectAppPath(self, fs, dir, child=None):
        o = fs.selectPath(unicode(dir, 'utf8'))
        if not o: return
        self.searchFs = o
        self.currDir = dir
        self.currSels = {}
        self.changeMenu()
        self.display(child)
        
    def selectItem(self, index):
        currSel = self.lb.current()
        if self.currItems is self.emptyItem and currSel == 0:
            self.onKeyLeft()
            return
        if index != currSel:
            self.lb.set_list(self.currItems, index)
            currSel = index
        itemName = self.currNames[currSel]
        if hasattr(itemName, 'name'):
            self.selectApp(itemName, self.searchFs)
            return
        p = pathjoin(self.currDir, itemName)
        if len(p) == 2 and p in self.e32drives:
            p = p + os.sep
        
        if path.isdir(p):
            self.selectDir(p)
        else:
            self.selectFile(p)

    def setSelectIndex(self, index):
        currSel = self.lb.current()
        if index != currSel:
            self.lb.set_list(self.currItems, index)
        
    def getSelectedItemName(self):            
        currSel = self.lb.current()
        return self.currNames[currSel]

    def getSelectedNames(self):
        "return multi-selection (check) names or the current selection"
        names = self.getCheckedNames()
        if names: return names
        return [self.getSelectedItemName()]

    def getSelectedDrives(self):
        if not self.currDir:
            drives = self.getSelectedNames()
            return [d for d in drives if isinstance(d, unicode)]
    
    def getCheckedNames(self):
        currSels = self.currSels
        return [name for name in currSels if currSels[name]]

    def isChecked(self, name):
        return self.currSels.get(name, 0)   # 1 or 0
    
    def getItemIndex(self, nameStartWith):
        names = self.currNames
        if names:
            if isinstance(names[0], tuple):
                names = [t[0] for t in names]
            elif hasattr(names[0], 'name'):
                names = [a.name for a in names]
        nextSel = self.lb.current() + 1
        c = nameStartWith.lower()
        for r in [xrange(nextSel, len(names)), xrange(0, nextSel)]:
            for i in r:
                if c == names[i][0].lower():
                    return i
        return -1

    def getFileNames(self):
        if self.searchFs:
            return [(name, dir) for name, dir in self.searchFs
                if not path.isdir(path.join(dir, name))]
        else:
            dir = self.currDir
            return [name for name in self.currNames
                if not path.isdir(path.join(dir, name))]
        
    def inputPathname(self, txt, name=None, defExt='', notExist=True):
        if isinstance(name, tuple):
            dir, name = name[1], name[0]
        else:
            dir = self.currDir
        name = appuifw.query(txt, u'text', name)
        while name:
            p = path.join(dir, name)
            if defExt:
                ext = getType(p)
                if not ext:
                    p += '.' + defExt
            if not path.isabs(p):
                alert("Requires an absolute path.")
                name = appuifw.query(txt, u'text', name)
            elif notExist and path.exists(p):
                name = appuifw.query(txt + " (%s exists)" % name, u'text', name)
            else:
                return p
            
    # events handler
    
    def onSelect(self):
        currSel = self.lb.current()
        self.selectItem(currSel)
        
    def onKeyLeft(self):
        """Display parent dir. if in search list, display current dir"""
        if isinstance(self.searchFs, (list, SearchList)):
            if isinstance(self.searchFs, list):
                self.selectDir(self.currDir)
            else:
                self.selectApp(None, self.searchFs)
            return
        (parent, name) = path.split(self.currDir)
        if parent:
            # if currDir is one of the drive
            if parent == self.currDir:
                self.selectDir('', parent[0:2])
            else:
                head = splithead(parent)
                if head in self._exts:
                    self.selectAppPath(self._exts[head], parent, self.searchFs)
                else:
                    self.selectDir(parent, name)
        else:
            self.selectDir('', self._exts.get(name))

    def onKeyRight(self):
        """Display selected dir/file"""
        currSel = self.lb.current()
        self.selectItem(currSel)

    def onKey(self, k):
        if not k.isalpha():
            k = self.keymod.key(ord(k))
            if not k: return
            if k == ' ':
                return self.onSelectUnselect()
            code = ord(k)
            if code == EKeyPageUp:
                return self.scrollList(-ListScrollPg)
            elif code == EKeyPageDown:
                return self.scrollList(ListScrollPg)
        i = self.getItemIndex(k)
        if i != -1:
            self.setSelectIndex(i)

    def onExit(self):
        self.exitApp()

    def onFocus(self, fg):
        if appuifw.app.body is self.atxt:   # in text editor
            self.keymod.clear()
            if fg:
                if self.pref['textmode']:
                    self.keyc.start()
            else:
                if self.keyc._listening:
                    self.keyc.stop()
        
        if (not fg) and self.cbAction:
            ac = self.cbAction
            if ac[0] == SCREENSHOT:
                self.keyc_ss.start()
                    
    def onTab(self, index):
        pass

    # menu events handler

    def onTextKey(self, keycode):
        if self.pref['textmode'] == '':    # normal text mode
            return
        k = chr(keycode)
        if not (k.isdigit() or k in '*#'):
            self.keymod.clear()
            return
        k = self.keymod.key(ord(k))
        if not k: return
        code = ord(k)
        if code == EKeyPageUp:
            self.scrollUp()
        elif code == EKeyPageDown:
            self.scrollDown()
        else:
            self.atxt.add(unicode(k))
            
    # SMS: New, Open, Save, Save As, Close,  Send
    def onNew(self):
        self.atxt.delete()
        self.atxtFile = ""
        self.showEditorPath()

    def onOpen(self):
        names = self.getFileNames()
        if not names:
            return
        lnames = isinstance(names[0], tuple) and [t[0] for t in names] or names
        i = appuifw.selection_list(lnames, 1)
        if i is None: return
        p = pathjoin(self.currDir, names[i])
        self.openText(p)

    def openText(self, p):
        try:
            self.atxt.set(readText(p))
            self.atxt.set_pos(0)
            self.atxtFile = p
            self.showEditorPath()
        except IOError, ioe:
            error(ioe)
        except Exception, e:
            alert(u"Not a text file.")
            
    def saveText(self, p):
        try:
            writeText(p, normText(self.atxt.get()))
            if p != self.atxtFile:
                self.atxtFile = p
                self.showEditorPath()
            return True
        except Exception, e:
            error(e)
            return False

    def editText(self, p, menu):
        appuifw.app.menu = menu
        appuifw.app.exit_key_handler = self.onClose
        appuifw.app.body = self.atxt
        self.keymod.clear()
        if self.pref['textmode']:
            self.keyc.start()
        self.onNew()
        if path.exists(p) and (not path.isdir(p)):
            self.openText(p)
            
    def onSave(self):
        if self.atxtFile:
            self.saveText(self.atxtFile)
        else:
            self.onSaveAs()

    def onSaveAs(self):
        if self.keyc._listening:
            self.keyc.stop()
        txt = MenuATxt[1][3]
        name = self.atxtFile and path.split(self.atxtFile)[1] or None
        p = self.inputPathname(txt, name, notExist=False)
        if p:
            self.saveText(p)
        if self.pref['textmode']:
            self.keyc.start()

    def onClose(self):
        self.atxt.clear()
        self.keymod.clear()
        if self.keyc._listening:
            self.keyc.stop()
        self.changeMenu()
        appuifw.app.exit_key_handler = self.onExit
        appuifw.app.body = self.lb
        self.refresh()

    def onSend(self):
        m = normText(self.atxt.get())
        if not m: return
        if self.keyc._listening:
            self.keyc.stop()
        txt = MenuSend[1][-1] + " to"
        to = appuifw.query(txt, u'text')
        if to:
            to = [t for t in [t.strip() for t in to.split(',')] if t]
            # support UCS2 sms (eg for CJK)
            enc = None
            try:
                str(m)
            except Exception, e:
                enc = 'UCS2'
            if enc:
                try: # require > 1.3.21
                    for w in to:
                        messaging.sms_send(w, m, enc)
                    alert(u"SMS (u) is sent.")
                except Exception, e:
                    alert(u"Require newer PyS60. (>= 1.3.21)")
            else: # default use 7bit
                for w in to:
                    messaging.sms_send(w, m)
                alert(u"SMS is sent.")
        if self.pref['textmode']:
            self.keyc.start()

    def settings(self):
        f = self.initPref()
        f.execute()
        
    def about(self):
        #alert(AboutApp)
        lbls = AboutApp.split('\n')
        fds = [(lbls[i], 'text', lbls[i+1]) for i in range(0, len(lbls), 2)]
        f = appuifw.Form(fds, appuifw.FFormViewModeOnly | appuifw.FFormDoubleSpaced)
        f.execute()

    def sendSMS(self):
        name = self.getSelectedItemName()
        if hasattr(name, 'name'): #app
            p = ''
        else:
            p = pathjoin(self.currDir, name)
        self.editText(p, self.atxtMenu)

    def sendFilesbyEmail(self):
        try:
            from email_util import sendMail
        except Exception, e:
            alert("Require python lib email, smtplib.")
            return
        pref = self.pref
        if not (pref.get('email') and pref.get('smtpHost')):
            alert("Require email and smtpHost settings to be set.")
            return
        # send email, attach file
        names = self.getSelectedNames()
        plist = [p for p in pathList(self.currDir, names) if not path.isdir(p)]
        t = appuifw.multi_query(u"Email to", u"Subject")
        if not t: return
        to, txt = t
        to = [t for t in [t.strip() for t in to.split(',')] if t]
        try:
            sendMail(pref['email'], to, txt, txt, plist, pref['smtpHost'])
            alert(u"Email is sent.")
        except Exception, e:
            alert(e)

    def sendFilesbyMMS(self):
        names = self.getSelectedNames()
        if not names: return
        plist = [p for p in pathList(self.currDir, names) if not path.isdir(p)]
        if not plist: return
        t = appuifw.multi_query(u"Send to", u"Subject")
        if not t: return
        to, txt = t
        plist = unicode_list(plist)
        try:
            if e32.s60_version_info >= (3,0):
                messaging.mms_send(to, txt, plist[0])
            else:
                import mmsmodule
                # Note: I added mms_sendtomany
                to = [t for t in [t.strip() for t in to.split(',')] if t]
                mmsmodule.mms_sendtomany(to, txt, plist)
                #mmsmodule.mms_send(to, txt, plist[0])
            alert(u"MMS is sent.")
        except ImportError, ie:
            alert("Require python lib mmsmodule.")
        except Exception, e:
            alert(e)

    def sendFilesbyBluetooth(self):
        names = self.getSelectedNames()
        if not names: return
        plist = [p for p in pathList(self.currDir, names) if not path.isdir(p)]
        if not plist: return
        #plist = unicode_list(plist)
        # Note: see bluetooth testing
        # ? can't find service (0, error)
        try:
            from lightblue import selectdevice, findservices, OBEX, obex
        except Exception, e:
            try:
                addr, services = socket.bt_obex_discover()
                serviceport = services.itervalues().next()
                for p in plist:
                    socket.bt_obex_send_file(addr, serviceport, p)
            except Exception, e:
                alert(e)
            return
        try:
            dev = selectdevice()
            services = findservices(dev[0], servicetype=OBEX)
            # eg. [('00:11:B1:08:FE:62', 4, 'OPP Server')]
            addr, serviceport, servicename = services[0]
            for p in plist:
                obex.sendfile(addr, serviceport, p)
        except Exception, e:
            alert(e)

    def searchApp(self, pattern):
        pattern = pattern.replace('*', '.*')
        rc = re.compile(pattern, re.I)
        fs = self.searchFs
        if isinstance(fs, SearchList):   # search from original contents
            items, names = fs.app.getListContents()
            fs = fs.app
        else:
            names = self.currNames
        return SearchList(fs, [o for o in names if rc.search(o.name)], self)
    
    def search(self, pattern, text=''):
        if self.currDir:
            fs = findFiles(self.currDir, pattern)
        else: # search all drives
            fs, sep = [], os.sep
            for d in e32.drive_list():
                fs.extend(findFiles(d + sep, pattern))
        if not (fs and text): return fs
        try:
            rc = re.compile(text, re.I)
        except re.error:
            # Tries to search for the given plain string.
            rc = re.compile(re.escape(text), re.I)
        return [item for item in fs if searchText(pathjoin('', item), rc)]
        
    def onSearch(self):
        #fds = [(u"Search for files", 'text', u"*.*"), (u"Containing text", 'text', u'')]
        #f = appuifw.Form(fds, appuifw.FFormEditModeOnly | appuifw.FFormDoubleSpaced)
        # Form will prompt save
        #s, t = appuifw.multi_query(u"Search for files", u"Containing text")
        # multi_query - both txt must be entered
        txt = u"Search for files containing text (use a comma to delimit, eg *.*, python"
        s = appuifw.query(txt, u'text', u"*.*")
        if not s: return
        l = s.split(',', 1)
        s, t = l[0], (len(l) == 2) and l[1].strip() or ''
        
        #head = splithead(self.currDir)
        if isinstance(self.searchFs, AppInterface): #head in self._exts:
            self.searchFs = self.searchApp(s)
        else:
            self.searchFs = self.search(s, t)
        # mod menus
        self.currSels = {}
        self.viewby = None
        self.changeMenu()
        self.display()
        
    def onNewFolder(self):
        txt = MenuFile[1][1]
        p = self.inputPathname(txt)
        if not p: return
        try:
            os.mkdir(p)
            self.refresh()
        except Exception, e:
            alert(e)
        
    def onRename(self):
        txt = MenuFile[1][2]
        name = self.getSelectedItemName()
        p = self.inputPathname(txt, name)
        if not p: return
        try:
            os.rename(pathjoin(self.currDir, name), p)
            self.display(path.split(p)[1])
        except Exception, e:
            alert(e)
        
    def onDelete(self):
        txt = MenuFile[1][3] + "?"
        if not appuifw.query(txt, u'query'): return
        names = self.getCheckedNames()
        selname = self.getSelectedItemName()
        if not names:
            names = [selname]
        try:
            for name in names:
                p = pathjoin(self.currDir, name)
                remove(p)
            if selname in names:
                selname = None
            self.display(selname)
        except Exception, e:
            alert(e)
        
    def onCut(self):
        self.cbAction = (CUT, self.currDir, tuple(self.getSelectedNames()))

    def onCopy(self):
        if self.currDir:
            self.cbAction = (COPY, self.currDir, tuple(self.getSelectedNames()))
        else:
            self.cbAction = (COPYDRIVE, self.currDir, tuple(self.getSelectedDrives()))

    def onPaste(self):
        if not self.cbAction:
            return
        ac = self.cbAction
        if ac[0] == COPY:
            copyList(ac[1], ac[2], self.currDir)
        elif ac[0] == CUT:
            moveList(ac[1], ac[2], self.currDir)
        elif ac[0] == COPYDRIVE:
            copyDrives(ac[2], self.currDir)
        else:
            self.cbAction = None
            return
        self.cbAction = (PASTE, ac)
        self.refresh()

    def onProperties(self):
        name = self.getSelectedItemName()
        if hasattr(name, 'name'): return #app
        if self.currDir:
            fmt = "%d %b %Y, %H:%M:%S"
            if isinstance(name, tuple):
                dir, name = name[1], name[0]
            else:
                dir = self.currDir
            p = path.join(dir, name)
            t = os.stat(p)
            m, n, d, l, u, g, s, ta, tm, tc = t
            # "Created", "Accessed" ? not supported
            lbls = ["Name", "Location", "Size", "Modified"]
            sz = "%s (%d)" % (viewSize(s, False), s)
            dm = strftime(fmt, localtime(tm))
            if type(dir) is not unicode:
                dir = unicode(dir, 'utf8')
            vals = [name, dir, sz, dm[0:7] + dm[9:]]
        else:
            lbls = ["Name", "Free sp"] #"Free space", can't see all
            sz = viewSize(sysinfo.free_drivespace()[name], False)
            vals = [name, sz]
        fds = [(unicode(lbls[i]), 'text', unicode(vals[i])) for i in range(0, len(lbls))]
        f = appuifw.Form(fds, appuifw.FFormViewModeOnly)
        f.execute()

    def onTagIt(self):
        itemName = self.getSelectedItemName()
        if isinstance(itemName, AppItem):
            a = itemName
            txt = u"Tag %s (use comma to separate tags eg. Games,card)" % a.name
            tags = a.tags and u','.join(a.tags) or u''
            tags = appuifw.query(txt, u'text', tags)
            if not tags: return
            tags = [tag.strip() for tag in tags.split(',')]
            app = self.getApp()
            app.tagItem(a, tags)
        else:
            alert("Select an application first to apply tagging.")
            
    def onSelectAll(self):
        self.currSels = dict([(name, 1) for name in self.currNames])
        self.refresh()

    def onInvertSelection(self):
        currSels = self.currSels
        self.currSels = dict([(name, 1) for name in self.currNames
                              if currSels.get(name, 0) == 0])
        self.refresh()

    def onSelectUnselect(self):
        name = self.getSelectedItemName()
        self.currSels[name] = (self.currSels.get(name, 0) == 0) and 1 or 0
        self.refresh()

    # zip
    def onAddto(self):
        p = self.inputPathname(u"Zip Archive filename", defExt='zip')
        if not p: return
        try:
            zipList(p, self.currDir, self.getSelectedNames())
            self.refresh()
        except Exception, e:
            alert(e)
            
    def onExtractfiles(self):
        name = self.getSelectedItemName()
        p = pathjoin(self.currDir, name)
        if not zipfile.is_zipfile(p):
            alert(u"%s is not a zip file." % p)
            return
        try:
            unzipDir(p, self.currDir)
            self.refresh()
        except Exception, e:
            alert(e)

    def onScreenshot(self):
        p = self.getScreenshotFile()
        if not p: return
        self.cbAction = (SCREENSHOT, p)
        # wait for app switch
        
    def onOwnScreenshot(self):
        p = self.getScreenshotFile()
        if not p: return
        # wait for query ui to be dismiss!?
        e32.ao_sleep(0, lambda: self.saveScreenshot(p))

    def onScreenshotKey(self, keycode):
        if keycode == EKeyLeftSoftkey or keycode == EKeyRightSoftkey:
            self.keyc_ss.stop()
            if keycode == EKeyRightSoftkey:
                self.cbAction = None
                return
            p = self.cbAction[1]
            e32.ao_sleep(0, lambda: self.saveScreenshot(p))
            
    def onViewBy(self, what):    
        if self.viewby == what:
            return
        self.viewby = what
        self.refresh()
        
    def viewbyName(self): self.onViewBy("Name")
    def viewbyType(self): self.onViewBy("Type")
    def viewbySize(self): self.onViewBy("Size")
    def viewbyDate(self): self.onViewBy("Date")

    def getScreenshotFile(self):
        if not self.pref['imageDir']:
            alert("Images directory setting is not set.")
            return
        txt = u"Save screenshot image (jpg or png)"
        p = self.inputPathname(txt, ('', self.pref['imageDir']), defExt='png', notExist=False)
        return p
    
    def saveScreenshot(self, p):
        try:
            img = graphics.screenshot()
            if type(p) is not unicode:
                p = unicode(p, 'utf8')
            img.save(p)
        except Exception, e:
            alert(e)
        if self.cbAction and self.cbAction[0] == SCREENSHOT:
            self.cbAction = None
            
    def scrollText(self, numlines):
        atxt = self.atxt
        pos = atxt.get_pos()
        txt = atxt.get()
        lines = txt.splitlines(True)
        n, col = linecolnum(pos, lines)
        n = n + numlines
        if n < 0:
            n = 0
        elif n >= len(lines):
            n = len(lines) - 1
        npos = position(n, col, lines)
        atxt.set_pos(npos)

    def scrollList(self, num):
        currSel = self.lb.current()
        newSel = currSel + num
        sz = len(self.currNames)
        if newSel < 0:
            newSel = 0
        elif newSel >= sz:
            newSel = sz - 1
        self.setSelectIndex(newSel)
        
    def scrollUp(self):
        if appuifw.app.body is self.atxt:   # in text editor
            self.scrollText(-TextScrollPg)

    def scrollDown(self):
        if appuifw.app.body is self.atxt:   # in text editor
            self.scrollText(TextScrollPg)


def lcase(str):
    return str[0].lower() + str[1:]

def getType(fname):
    ext = path.splitext(fname)[1]
    return ext[1:].lower()  # use ext
def getSize(fname): return path.getsize(fname)
def getDate(fname): return path.getmtime(fname) # use last modified 

def viewType(val): return val.ljust(4)[0:4]     # ?
def viewSize(val, bJust=True):
    if val == Es:
        return val
    if val < 0x400:
        s = "%.2f KB" % (float(val)/0x400)
    elif val < 0x100000:
        s = "%.1f KB" % (float(val)/0x400)
    elif val < 0x40000000:
        s = "%.1f MB" % (float(val)/0x100000)
    else:
        s = "%.1f GB" % (float(val)/0x40000000)
    if bJust:
        return s.rjust(ListAttrMaxWidth)
    return s
    
def viewDate(val):
    #return strftime("%d%b %y", localtime(val))
    s = strftime("%d%b %Y", localtime(val))
    return s[0:6] + s[8:]


def listdir(dir, viewby=None):
    files = [unicode(name, 'utf8') for name in os.listdir(dir)]
    return listfiles(files, viewby, path.join, dir, False)

def listtuplefiles(files, viewby=None):
    dirList, fileList = listfiles(files, viewby, pathjoin)
    dirList.extend(fileList)
    return dirList

def listfiles(files, viewby=None, pathjoinfn=path.join, dir='', namesort=True):
    """folders, files are listed separately"""
    dirList = []
    fileList = []
    for name in files:
        p = pathjoinfn(dir, name)
        #name = unicode(name)
        if path.isdir(p):
            dirList.append(name)
        else:
            fileList.append(name)
    if (not viewby) or (viewby == "Name" and not namesort):
        return (dirList, fileList)
    if viewby == "Name":
        dirList.sort()
        fileList.sort()
        return (dirList, fileList)
    # sort listing based on attribute
    m = listdir.func_globals
    attr = m['get' + viewby]
    if viewby == "Date":
        return (sortFiles(dir, dirList, attr, pathjoinfn), sortFiles(dir, fileList, attr, pathjoinfn))
    dirList = [(name, Es) for name in dirList]
    return (dirList, sortFiles(dir, fileList, attr, pathjoinfn))

def sortFiles(dir, files, attr, pathjoinfn=path.join):
    slist = []
    for name in files:
        p = pathjoinfn(dir, name)
        slist.append((attr(p), name))
    slist.sort()
    # return with (name, attr)
    return [(n, a) for a, n in slist]

def remove(p):
    if path.isdir(p):
        return remove_tree(p)
    else:
        return os.remove(p)

def removeList(dir, names):
    rlist = []
    try:
        for name in names:
            remove(pathjoin(dir, name))
            rlist.append(name)
    except Exception, e:
        alert(e)
    return rlist
    
def copy(dir, name, dest):
    if isinstance(name, tuple):
        dir, name = name[1], name[0]
    p = path.join(dir, name)
    dp = path.join(dest, name)
    if path.isdir(p):
        return copy_tree(p, dp)
    else:
        return copy_file(p, dp)

def copyList(dir, names, dest):
    if dir == dest:
        return
    clist = []
    try:
        for name in names:
            if copy(dir, name, dest) is not None:
                clist.append(name)
    except CopyStopError, se:
        pass
    except Exception, e:
        alert(e)
    return clist

def copyDrives(drives, dest):
    clist, sep = [], os.sep
    try:
        for d in drives:
            copy_tree(d + sep, path.join(dest, d[0]))
            clist.append(d)
    except CopyStopError, se:
        pass
    except Exception, e:
        alert(e)
    return clist

def move(dir, name, dest):
    if isinstance(name, tuple):
        dir, name = name[1], name[0]
    p = path.join(dir, name)
    dp = path.join(dest, name)
    return os.rename(p, dp)

def moveList(dir, names, dest):
    if dir == dest:
        return
    # check drive
    if dir[0] == dest[0]:
        try:
            for name in names:
                move(dir, name, dest)
        except Exception, e:
            alert(e)
    else: # copy/del
        clist = copyList(dir, names, dest)
        if len(clist) == len(names):
            removeList(dir, names)
        else: # remove copied?
            removeList(dest, clist)

def pathList(dir, names):
    if not names: return names
    if isinstance(names[0], tuple):
        return [path.join(dir, name) for name, dir in names]
    else:
        return [path.join(dir, name) for name in names]
    
def zipList(fp, dir, names):
    if not names: return
    zip = zipfile.ZipFile(fp, 'w', zipfile.ZIP_DEFLATED)
    dir = str(dir)
    if isinstance(names[0], tuple):
        for name, dir in names:
            zipItem(zip, dir, name.encode('utf8')) #str(name))
    else:
        for name in names:
            zipItem(zip, dir, name.encode('utf8'))
        #for name in map(str, names):
        #    zipItem(zip, dir, name)
    zip.close()

def zipItem(zip, dir, name):
    p = path.join(dir, name)
    if path.isdir(p):
        zip_tree(zip, p, True)
    else:
        zip.write(p, name)
    
def pathjoin(dir, item):
    if isinstance(item, tuple): dir, item = item[1], item[0]
    return path.join(dir, item)

def searchTextInFile(f, rc):
    for line in f:
        if rc.search(line):
            return line
        
# allow utf_16
def searchText(p, rc):
    if path.isdir(p): return
    # test with codecs utf_16 doesn't read
    if fileisUtf16(p): # use readText to read all
        try:
            return searchTextInFile(readText(p).split('\n'), rc)
        except Exception, e:
            return
    f = s = None
    try:
        #f = codecs.open(p, 'rb', 'utf_16')
        f = file(p, 'r')
        s = searchTextInFile(f, rc)
        f.close()
    except Exception, e:
        if f: f.close()
    return s

# check if file uses BOM -> Utf16
def fileisUtf16(p):
    b = False
    f = None
    try:
        f = file(p, 'r')
        b = f.read(2) == codecs.BOM
    finally:
        if f: f.close()
    return b

# allow utf_16 , writeText
def readText(p):
    f = file(p, 'r')
    t = f.read()
    f.close()
    try:
        return unicode(t)
    except Exception, e:
        return unicode(t, 'utf_16')
    #return t

def normText(t):
    return t.replace(u'\u2029', '\n') # os.linesep

def writeText(p, t):
    try:
        t = str(t)
    except Exception, e:
        t = t.encode('utf_16')
    f = file(p, 'w+')
    f.write(t)
    f.close()

def splithead(p):
    i, count = 0, len(p)
    while i < count and p[i] not in '/\\':
        i = i + 1
    return p[0:i]

def _str_data(rd, name):
    rdc = ",\n    ".join(["\"%s\": '%s'" % (k.replace('\\', '\\\\').encode('utf8'), v.replace('\\', '\\\\').encode('utf8'))
                          for k, v in rd.iteritems()])
    return name + " = {\n    " + rdc + "}\n"
def _str_pref(rd): return _str_data(rd, "Prefs")
def _str_tags(rd): return _str_data(rd, "Tags")

def linecolnum(pos, lines):
    count = 0
    for i, line in zip(range(0, len(lines)), lines):
        count = count + len(line)
        if pos < count:
            return i, pos - count + len(line)
    return len(lines), 0

def position(num, col, lines):
    count = 0
    for line in lines[0:num]:
        count = count + len(line)
    col = min(col, len(lines[num]) - 1)
    if col < 0: col = 0
    return count + col

def alert(o):
    appuifw.note(unicode(o), u"info")
def error(o):
    appuifw.note(unicode(o), u"error")
def checklayout():
    if not hasattr(appuifw, 'EScreen'):
        return
    try:
        global ListScrollPg, TextScrollPg
        layout = appuifw.app.layout
        size, pos = layout(appuifw.EMainPane)
        csize, cpos = layout(appuifw.EControlPane)
        ListScrollPg = (size[1] - int(round(0.8*csize[1])))/csize[1]
        TextScrollPg = size[1]/16
        #alert((size, pos, csize, cpos, ListScrollPg, TextScrollPg))
    except Exception, e:
        print e
    

    
def run(dir=None):
    try:
        if dir is None:
            dir = path.split(__file__)[0]
        #Explorer(dir).run()
        exp = Explorer(dir)
        e32.ao_sleep(0, exp.run)
    except Exception, e:
        alert(e)
        
if __name__ == '__main__':
    import sys
    fn = sys.argv[0]
    (d, name) = path.split(fn)
    run(d)
        
