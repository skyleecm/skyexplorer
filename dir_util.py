# dir_util.py
#    @copyright: 2007 -  Lee Chee Meng skyleecm@gmail.com
#    @License: GPL

from __future__ import generators
import os
from os import path, listdir, makedirs, chmod, error
from shutil import copyfile    # copy2
from appuifw import query
#from e32 import file_copy 
from fnmatch import filter
from time import localtime
from stat import S_IMODE, S_ISDIR
import zipfile

pSep = os.sep
if hasattr(os, 'altsep'):
    pSep += os.altsep
if '/' not in pSep:
    pSep += '/'


def findFiles(dir, pattern):
    """Return list of (filename, dir) that matches Unix filename pattern."""
    fs = []
    for d, dirs, files in os.walk(dir):
        fs.extend([(n, d) for n in filter(dirs, pattern)])
        fs.extend([(n, d) for n in filter(files, pattern)])
    return fs

class CopyStopError(Exception):
    pass

def copy_file(src, dst, txt=u"Do you want to continue?"):
    try:
        copyfile(src, dst) #file_copy(dst, src)
        return True
    except Exception, e:
        es = unicode(e)
        if not query("%s\n%s" % (es, txt), u'query'):
            raise CopyStopError(es)

def copy_tree(src, dst):
    """Copy an entire directory tree 'src' to a new location 'dst'.  Both
       'src' and 'dst' must be directory names. Return the list of files that 
       were copied. """
    if not path.isdir(src):
        raise Exception, "cannot copy tree '%s': not a directory" % src
              
    outputs = []
    cmds = []
    copy_cmd(src, dst, cmds)
    for cmd, f in cmds:
        if cmd is copy_file:
            if copy_file(f[0], f[1]):
                outputs.append(f[1])
        else:
            cmd(f)
    return outputs

def copy_cmd(src, dst, cmds):
    names = os.listdir(src)
    if not path.exists(dst):
        cmds.append((os.mkdir, dst))
    for n in names:
        src_name = path.join(src, n)
        dst_name = path.join(dst, n)
        if path.isdir(src_name):
            copy_cmd(src_name, dst_name, cmds)
        else:
            cmds.append((copy_file, [src_name, dst_name]))

def remove_tree(dir):
    """Recursively remove an entire directory tree.  
       Return the list of files that were removed. """
    outputs = []
    cmds = []
    remove_cmd(dir, cmds)
    for cmd, f in cmds:
        cmd(f)
        if cmd is os.remove:
            outputs.append(f)
    return outputs

def remove_cmd(dir, cmds):
    for f in os.listdir(dir):
        real_f = path.join(dir, f)
        if path.isdir(real_f) and not path.islink(real_f):
            remove_cmd(real_f, cmds)
        else:
            cmds.append((os.remove, real_f))
    cmds.append((os.rmdir, dir))

def mkpath(p, mode):
    if path.isdir(p): return
    makedirs(p, mode)
    
# zip dir (dir entry ends with /)
def zip_tree(zip, dir, asEntry=False):
    if asEntry: # dir's name is in the zip file
        rd = path.split(dir)[0]
    else:       # dir is root in the zip file
        rd = dir
    dlen = (rd[-1] in pSep) and len(rd) or len(rd) + 1
    if asEntry and dir[-1] not in pSep:
        p = dir + os.sep
        zip.writestr(zipinfo(p, dlen), '')
    for d, dirs, files in os.walk(dir):
        for f in files:
            p = path.join(d, f)
            zip.write(p, p[dlen:])
        for f in dirs:
            p = path.join(d, f) + os.sep
            zip.writestr(zipinfo(p, dlen), '')

# unzip have to work if dir entry is not in the zip file
def unzip(zip, dir):
    for zi in zip.infolist():
        fn = zi.filename
        m = zi.external_attr >> 16
        if S_ISDIR(m) or fn[-1] in pSep:
            p = path.join(dir, fn[0:-1])
            mkpath(p, S_IMODE(m))
        else:
            p = path.join(dir, fn)
            mkpath(path.split(p)[0], 0777)
            f = file(p, 'w+')
            f.write(zip.read(fn))
            f.close()
            chmod(p, S_IMODE(m))

def zipinfo(p, rlen):
    t = os.stat(p)
    zi = zipfile.ZipInfo(p[rlen:], localtime(t[8])[0:6])
    zi.external_attr = t[0] << 16
    return zi

def zipDir(fp, dir):
    zip = zipfile.ZipFile(fp, 'w', zipfile.ZIP_DEFLATED)
    zip_tree(zip, dir, True)
    zip.close()

def unzipDir(fp, dir):
    zip = zipfile.ZipFile(fp, 'r')
    unzip(zip, dir)
    zip.close()

# copy here, os.walk
def walk(top, topdown=True, onerror=None):
    from os.path import join, isdir, islink

    # We may not have read permission for top, in which case we can't
    # get a list of the files the directory contains.  os.path.walk
    # always suppressed the exception then, rather than blow up for a
    # minor reason when (say) a thousand readable directories are still
    # left to visit.  That logic is copied here.
    try:
        # Note that listdir and error are globals in this module due
        # to earlier import-*.
        names = listdir(top)
    except error, err:
        if onerror is not None:
            onerror(err)
        return

    dirs, nondirs = [], []
    for name in names:
        if isdir(join(top, name)):
            dirs.append(name)
        else:
            nondirs.append(name)

    if topdown:
        yield top, dirs, nondirs
    for name in dirs:
        path = join(top, name)
        if not islink(path):
            for x in walk(path, topdown, onerror):
                yield x
    if not topdown:
        yield top, dirs, nondirs

if not hasattr(os, 'walk'):
    os.walk = walk

