''' Get windows special folders without pythonwin
    Example:
            import specialfolders
            start_programs = specialfolders.get(specialfolders.PROGRAMS)

Code is public domain, do with it what you will. 

Luke Pinner - Environment.gov.au, 2010 February 10
'''

#Imports use _syntax to mask them from autocomplete IDE's
import ctypes as _ctypes
from ctypes.wintypes import HWND as _HWND, HANDLE as _HANDLE,DWORD as _DWORD,LPCWSTR as _LPCWSTR,MAX_PATH as _MAX_PATH, create_unicode_buffer as _cub
_SHGetFolderPath = _ctypes.windll.shell32.SHGetFolderPathW

#public special folder constants
DESKTOP=                             0
PROGRAMS=                            2
MYDOCUMENTS=                         5
FAVORITES=                           6
STARTUP=                             7
RECENT=                              8
SENDTO=                              9
STARTMENU=                          11
MYMUSIC=                            13
MYVIDEOS=                           14
NETHOOD=                            19
FONTS=                              20
TEMPLATES=                          21
ALLUSERSSTARTMENU=                  22
ALLUSERSPROGRAMS=                   23
ALLUSERSSTARTUP=                    24
ALLUSERSDESKTOP=                    25
APPLICATIONDATA=                    26
PRINTHOOD=                          27
LOCALSETTINGSAPPLICATIONDATA=       28
ALLUSERSFAVORITES=                  31
LOCALSETTINGSTEMPORARYINTERNETFILES=32
COOKIES=                            33
LOCALSETTINGSHISTORY=               34
ALLUSERSAPPLICATIONDATA=            35

def get(intFolder):
    _SHGetFolderPath.argtypes = [_HWND, _ctypes.c_int, _HANDLE, _DWORD, _LPCWSTR]
    auPathBuffer = _cub(_MAX_PATH)
    exit_code=_SHGetFolderPath(0, intFolder, 0, 0, auPathBuffer)
    return auPathBuffer.value


if __name__ == "__main__":
	import os
	print get(STARTUP)
	open(get(STARTUP)+"\\zeronet.cmd", "w").write("cd /D %s\r\nzeronet.py" % os.getcwd())