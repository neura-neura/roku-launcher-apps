"""Create the launcher library for Roku Plus 1.7.2, leaving the input ZIP intact."""
import re
import stat
from pathlib import PurePosixPath
from zipfile import ZipFile


def adapt_plus(path):
    with ZipFile(path) as archive:
        files = {}
        for item in archive.infolist():
            p = PurePosixPath(item.filename)
            if item.is_dir() or p.is_absolute() or ".." in p.parts or stat.S_ISLNK(item.external_attr >> 16):
                continue
            if p.parts[0] in ("components", "source", "data", "images") or p.name == "CREDITS-HD.txt":
                if item.filename != "source/main.brs":
                    files[item.filename] = archive.read(item)
        manifest = archive.read("manifest").decode()

    if "title=Roku Plus por JGL Customs" not in manifest or "build_version=2" not in manifest:
        raise ValueError("The ZIP is not the tested Roku Plus version")

    for name, data in list(files.items()):
        if not name.endswith((".xml", ".brs")):
            continue
        text = re.sub(r"(?<![\w:])pkg:/", "libpkg:/", data.decode())
        if name.endswith(".xml"):
            directory = PurePosixPath(name).parent
            text = re.sub(r'(<script\b[^>]*\buri=")([^":]+)(")', lambda m:
                          m[1] + f"libpkg:/{directory / m[2]}" + m[3], text)
        files[name] = text.encode()

    name = "components/PlusScene.xml"
    xml = files[name].decode()
    before = '<component name="PlusScene" extends="Scene">'
    if xml.count(before) != 1:
        raise ValueError("Could not find the Roku Plus entry scene")
    files[name] = xml.replace(before, '''<component name="PlusModule" extends="Group">
  <interface>
    <field id="running" type="boolean" onChange="plusRunningChanged" />
  </interface>''').encode()

    name = "components/PlusScene.brs"
    code = files[name].decode().replace("\r\n", "\n")
    original = 'sub init()\n    m.top.backgroundColor = "0x09090BFF"\n    m.top.focusable = true\n'
    if code.count(original) != 1:
        raise ValueError("Could not find the expected Roku Plus initialization")
    code = code.replace(original, 'sub init()\nend sub\n\nsub plusStart()\n')
    original = '    if handleLibraryKey(key) then return true'
    if code.count(original) != 1:
        raise ValueError("Could not find the expected Roku Plus navigation")
    code = code.replace(original, '''    if key = "back" and not m.busy
        if m.view = "home" or (m.view = "setup-tv" and not m.setupFromSettings) then return false
    end if
    if handleLibraryKey(key) then return true''')
    code = code.replace("m.top.dialog = dialog", "plusShowDialog(dialog)")
    code = code.replace('    dialog.close = true\nend sub', '''    dialog.close = true
    scene = m.top.getScene()
    if scene <> invalid
        if scene.dialog <> invalid and scene.dialog.isSameNode(dialog) then scene.dialog = invalid
    end if
end sub''')
    controller = "components/PlusLibraryController.brs"
    files[controller] = files[controller].replace(b"m.top.dialog = dialog", b"plusShowDialog(dialog)")
    code += '''

sub plusShowDialog(dialog as Object)
    scene = m.top.getScene()
    if scene <> invalid then scene.dialog = dialog
end sub

sub plusRunningChanged()
    if m.top.running
        plusStart()
        return
    end if
    if m.jglVActive then closeJglV()
    releaseDialog()
    cancelRequest()
    cancelHomeRequests()
    stopLivePreview()
    m.lease.control = "stop"
    m.noteTimer.control = "stop"
    if m.leaseTask <> invalid then m.leaseTask.cancelRequested = true
    m.player.unobserveField("closed")
    m.player.unobserveField("closedRequest")
    m.player.callFunc("closePlayback")
end sub
'''
    files[name] = code.encode()
    files["manifest"] = (
        "title=Roku Plus por JGL Customs\nmajor_version=1\nminor_version=7\n"
        "build_version=2\nrsg_version=1.3\nbs_const=CONST_DEBUG=false\n"
    ).encode()
    return files
