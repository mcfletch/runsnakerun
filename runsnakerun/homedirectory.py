"""Attempt to determine the current user's "system" directories"""
from __future__ import absolute_import, print_function

try:
    ##	raise ImportError
    from win32com.shell import shell, shellcon
except ImportError:
    shell = None
try:
    from six.moves import winreg as winreg
except ImportError:
    winreg = None
import os, sys

if sys.platform == 'darwin':
    RELATIVE_CONFIG = 'Library/Preferences'
else:
    RELATIVE_CONFIG = '.config'

## The registry keys where the SHGetFolderPath values appear to be stored
r"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders"
r"HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders"


def winreg_getShellFolder(name):
    """Get a shell folder by string name from the registry"""
    k = six.moves.winreg.OpenKey(
        six.moves.winreg.HKEY_CURRENT_USER,
        r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders",
    )
    try:
        # should check that it's valid? How?
        return six.moves.winreg.QueryValueEx(k, name)[0]
    finally:
        six.moves.winreg.CloseKey(k)


def shell_getShellFolder(type):
    """Get a shell folder by shell-constant from COM interface"""
    return shell.SHGetFolderPath(
        0,  # null hwnd
        type,  # the (roaming) appdata path
        0,  # null access token (no impersonation)
        0,  # want current value, shellcon.SHGFP_TYPE_CURRENT isn't available, this seems to work
    )


def appdatadirectory():
    """Attempt to retrieve the current user's app-data directory

    This is the location where application-specific
    files should be stored.  On *nix systems, this will
    be the ${HOME}/{RELATIVE_CONFIG} directory.  
    On Win32 systems, it will be
    the "Application Data" directory.  Note that for
    Win32 systems it is normal to create a sub-directory
    for storing data in the Application Data directory.
    """
    if shell:
        # on Win32 and have Win32all extensions, best-case
        return shell_getShellFolder(shellcon.CSIDL_APPDATA)
    if winreg:
        # on Win32, but no Win32 shell com available, this uses
        # a direct registry access, likely to fail on Win98/Me
        return winreg_getShellFolder('AppData')
    # okay, what if for some reason winreg is missing? would we want to allow ctypes?
    ## default case, look for name in environ...
    for name in ['APPDATA', 'HOME']:
        if name in os.environ:
            if name == 'APPDATA':
                return os.environ[name]
            return os.path.join(os.environ[name], RELATIVE_CONFIG)
    # well, someone's being naughty, see if we can get ~ to expand to a directory...
    possible = os.path.abspath(os.path.expanduser('~/%s'%(RELATIVE_CONFIG,)))
    if os.path.exists(possible):
        return possible
    try:
        os.makedirs(possible)
    except Exception:
        pass
    raise OSError(
        """Unable to determine user's application-data directory, no ${HOME} or ${APPDATA} in environment, unable to create %s"""%(
            possible,
        )
    )


if __name__ == "__main__":
    print('AppData', appdatadirectory())
