import concurrent.futures
import hashlib
import os
import json
import random
import re
import sys
import time
import urllib.parse
import xbmc
import xbmcvfs
import xbmcaddon
import xml.etree.ElementTree as etree

ADDON    = xbmcaddon.Addon()
ADDONID = ADDON.getAddonInfo('id')
LANGUAGE = ADDON.getLocalizedString

# supported image types by the screensaver
IMAGE_TYPES = ['.jpg', '.jpeg', '.png', '.tif', '.tiff', '.gif', '.pcx', '.bmp', '.tga', '.ico', '.nef', '.webp', '.jp2', '.apng']
HEIF_TYPES = ['.heic', '.heif']
MPO_TYPES = ['.mpo']
RAW_TYPES = ['.3fr', '.arw', '.cr2', '.crw', '.dcr', '.dng', '.erf', '.kdc', '.mdc', '.mef', '.mos', '.mrw', '.nef', '.nrw', '.orf', '.pef', '.ppm', '.raf', '.raw', '.rw2', '.srw', '.x3f']
CACHEFOLDER = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
CACHEFILE = os.path.join(CACHEFOLDER, 'cache_%s')
RESUMEFILE = os.path.join(CACHEFOLDER, 'offset')
# threads used to list directories during a scan. 1 disables the pool entirely
# and walks serially, which is also the reference behaviour the tests compare to
WALK_WORKERS = 8
ASFILE = xbmcvfs.translatePath('special://profile/advancedsettings.xml')

def log(txt):
    message = '%s: %s' % (ADDONID, txt)
    xbmc.log(msg=message, level=xbmc.LOGDEBUG)

def checksum(path):
    return hashlib.md5(path).hexdigest()

def create_cache(path, hexfile, randomize, current_images=None):
    images = walk(path)
    if not xbmcvfs.exists(CACHEFOLDER):
        xbmcvfs.mkdir(CACHEFOLDER)
    # remove old cache files, but preserve settings and the resume offset
    dirs, files = xbmcvfs.listdir(CACHEFOLDER)
    preserve = {'settings.xml', os.path.basename(RESUMEFILE)}
    for item in files:
        if item not in preserve:
            xbmcvfs.delete(os.path.join(CACHEFOLDER, item))
    if images:
        if randomize:
            if current_images:
                # preserve existing shuffle order: keep known images in place,
                # insert new ones at random positions, drop removed ones
                new_paths = set(img[0] for img in images)
                images_by_path = {img[0]: img for img in images}
                # retain existing order, removing any files that have since been deleted
                ordered = [img for img in current_images if img[0] in new_paths]
                # insert genuinely new files at random positions
                added = [images_by_path[p] for p in new_paths - set(img[0] for img in current_images)]
                for img in added:
                    ordered.insert(random.randint(0, len(ordered)), img)
                images = ordered
            else:
                random.seed()
                random.shuffle(images)
        save_cache(images, hexfile)

def save_cache(images, hexfile):
    # create cache file
    if not xbmcvfs.exists(CACHEFOLDER):
        xbmcvfs.mkdir(CACHEFOLDER)
    try:
        cache = xbmcvfs.File(CACHEFILE % hexfile, 'w')
        json.dump(images, cache)
        cache.close()
    except:
        log('failed to save cachefile')

def get_excludes():
    regexes = []
    if xbmcvfs.exists(ASFILE):
        try:
            tree = etree.parse(ASFILE)
            root = tree.getroot()
            excludes = root.find('pictureexcludes')
            if excludes is not None:
                for expr in excludes:
                    regexes.append(expr.text)
        except:
            pass
    return regexes

def _natural_key(name):
    return [int(part) if part.isdigit() else part for part in re.split('([0-9]+)', name)]

def _image_extensions():
    # the imagedecoder addons are what make these formats displayable, so the
    # set depends on what is installed. Built once per scan rather than being
    # appended onto the module-level IMAGE_TYPES on every folder visited.
    extensions = list(IMAGE_TYPES)
    if xbmc.getCondVisibility('System.HasAddon(imagedecoder.heif)'):
        extensions += HEIF_TYPES
    if xbmc.getCondVisibility('System.HasAddon(imagedecoder.mpo)'):
        extensions += MPO_TYPES
    if xbmc.getCondVisibility('System.HasAddon(imagedecoder.raw)'):
        extensions += RAW_TYPES
    return frozenset(extensions)

def _excluded(name, excludes):
    # check pictureexcludes from as.xml
    for regex in excludes:
        if regex.search(name):
            return True
    return False

def _entry_folders(path):
    # multipath support
    if path.startswith('multipath://'):
        # get all paths from the multipath
        return [urllib.parse.unquote_plus(item) for item in path[12:-1].split('/')]
    return [path]

def _listdir_plugin(folder):
    getroot = xbmc.executeJSONRPC('{"jsonrpc":"2.0", "method":"Files.GetDirectory", "params":{"directory":"%s", "sort":{"method":"label"}}, "id":1 }' % folder)
    root = json.loads(getroot)
    dirs = []
    files = []
    if 'result' in root and 'files' in root["result"]:
        for item in root["result"]["files"]:
            if item["filetype"] == "file":
                files.append(item)
            elif item["filetype"] == "directory":
                dirs.append(item["file"])
    return dirs, files

def _scan_plugin(folder, excludes, extensions, recursive):
    # plugin:// directories come from JSON-RPC, which returns dicts rather than
    # names and full paths rather than children, so they cannot share the VFS
    # listing path
    images = []
    dirs, files = _listdir_plugin(folder)
    log('dirs: %s' % len(dirs))
    log('files: %s' % len(files))
    for item in files:
        # filter out all images
        if os.path.splitext(item["label"])[1].lower() in extensions and not _excluded(item["label"], excludes):
            images.append([item["file"], item["label"]])
    if recursive:
        for item in dirs:
            if _excluded(item, excludes):
                continue
            # a plugin may hand back a directory it cannot actually serve,
            # so these keep the existence check
            if xbmcvfs.exists(xbmcvfs.translatePath(item)):
                images += _scan(item, excludes, extensions, recursive)
            else:
                log('folder does not exist')
    return images

def _scan(folder, excludes, extensions, recursive):
    # serial walk. Kept as the reference the threaded version is compared
    # against, and used directly for plugin:// trees.
    if folder.startswith('plugin://'):
        return _scan_plugin(folder, excludes, extensions, recursive)
    subfolders, images = _list_folder(folder, excludes, extensions)
    if recursive:
        # recursively scan all subfolders
        for subfolder in subfolders:
            images += _scan(subfolder, excludes, extensions, recursive)
    return images

def _list_folder(folder, excludes, extensions):
    # one directory: the images in it, and the subfolders worth descending into
    dirs, files = xbmcvfs.listdir(folder)
    log('dirs: %s' % len(dirs))
    log('files: %s' % len(files))
    # natural sort
    files.sort(key=_natural_key)
    images = []
    for item in files:
        # filter out all images
        if os.path.splitext(item)[1].lower() in extensions and not _excluded(item, excludes):
            images.append([os.path.join(folder,item), item])
    # make sure paths end with a slash
    subfolders = [os.path.join(folder,item,'') for item in dirs if not _excluded(item, excludes)]
    return subfolders, images

def _scan_parallel(root, excludes, extensions, recursive):
    # listdir is one round trip per directory and the serial walk pays them one
    # after another, so a deep tree costs directory count x latency. The calls
    # are independent, so overlapping them hides most of it.
    listing = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=WALK_WORKERS) as pool:
        pending = {pool.submit(_list_folder, root, excludes, extensions): root}
        while pending:
            done, _ = concurrent.futures.wait(pending, return_when=concurrent.futures.FIRST_COMPLETED)
            for future in done:
                folder = pending.pop(future)
                subfolders, images = future.result()
                listing[folder] = (subfolders, images)
                if recursive:
                    for subfolder in subfolders:
                        pending[pool.submit(_list_folder, subfolder, excludes, extensions)] = subfolder
    # Directories complete in whatever order the network returns them, so the
    # output is rebuilt from the recorded structure rather than from completion
    # order: depth first, subfolders in the order listdir gave them. That is
    # what the serial walk produces, and the resume offset is an index into it.
    images = []
    stack = [root]
    while stack:
        folder = stack.pop()
        subfolders, folder_images = listing[folder]
        images += folder_images
        if recursive:
            stack.extend(reversed(subfolders))
    return images

def walk(path):
    # settings, excludes and the decodable extension set do not vary per
    # folder. Reading them once per scan instead of once per directory is what
    # makes a deep tree over SMB bearable.
    started = time.time()
    excludes = [re.compile(expr) for expr in get_excludes()]
    extensions = _image_extensions()
    recursive = xbmcaddon.Addon().getSettingBool('recursive')
    images = []
    for folder in _entry_folders(path):
        if xbmcvfs.exists(xbmcvfs.translatePath(folder)):
            # plugin:// directories come from JSON-RPC, not the VFS: low fan-out
            # and a different failure mode, so they stay on the serial path
            if WALK_WORKERS > 1 and not folder.startswith('plugin://'):
                images += _scan_parallel(folder, excludes, extensions, recursive)
            else:
                images += _scan(folder, excludes, extensions, recursive)
        else:
            log('folder does not exist')
    # the number to watch in kodi.log when judging a scan on real hardware
    log('scan finished: %i images in %.2fs (%i workers)' % (len(images), time.time() - started, WALK_WORKERS))
    return images
