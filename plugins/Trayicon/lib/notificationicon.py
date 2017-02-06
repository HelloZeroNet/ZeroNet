# Pure ctypes windows taskbar notification icon
# via https://gist.github.com/jasonbot/5759510
# Modified for ZeroNet

import ctypes
import ctypes.wintypes
import os
import uuid
import time
import gevent

__all__ = ['NotificationIcon']

# Create popup menu

CreatePopupMenu = ctypes.windll.user32.CreatePopupMenu
CreatePopupMenu.restype = ctypes.wintypes.HMENU
CreatePopupMenu.argtypes = []

MF_BYCOMMAND    = 0x0
MF_BYPOSITION   = 0x400

MF_BITMAP       = 0x4
MF_CHECKED      = 0x8
MF_DISABLED     = 0x2
MF_ENABLED      = 0x0
MF_GRAYED       = 0x1
MF_MENUBARBREAK = 0x20
MF_MENUBREAK    = 0x40
MF_OWNERDRAW    = 0x100
MF_POPUP        = 0x10
MF_SEPARATOR    = 0x800
MF_STRING       = 0x0
MF_UNCHECKED    = 0x0

InsertMenu = ctypes.windll.user32.InsertMenuW
InsertMenu.restype = ctypes.wintypes.BOOL
InsertMenu.argtypes = [ctypes.wintypes.HMENU, ctypes.wintypes.UINT, ctypes.wintypes.UINT, ctypes.wintypes.UINT, ctypes.wintypes.LPCWSTR]

AppendMenu = ctypes.windll.user32.AppendMenuW
AppendMenu.restype = ctypes.wintypes.BOOL
AppendMenu.argtypes = [ctypes.wintypes.HMENU, ctypes.wintypes.UINT, ctypes.wintypes.UINT, ctypes.wintypes.LPCWSTR]

SetMenuDefaultItem = ctypes.windll.user32.SetMenuDefaultItem
SetMenuDefaultItem.restype = ctypes.wintypes.BOOL
SetMenuDefaultItem.argtypes = [ctypes.wintypes.HMENU, ctypes.wintypes.UINT, ctypes.wintypes.UINT]

class POINT(ctypes.Structure):
    _fields_ = [ ('x', ctypes.wintypes.LONG),
                 ('y', ctypes.wintypes.LONG)]

GetCursorPos = ctypes.windll.user32.GetCursorPos
GetCursorPos.argtypes = [ctypes.POINTER(POINT)]

SetForegroundWindow = ctypes.windll.user32.SetForegroundWindow
SetForegroundWindow.argtypes = [ctypes.wintypes.HWND]

TPM_LEFTALIGN       = 0x0
TPM_CENTERALIGN     = 0x4
TPM_RIGHTALIGN      = 0x8

TPM_TOPALIGN        = 0x0
TPM_VCENTERALIGN    = 0x10
TPM_BOTTOMALIGN     = 0x20

TPM_NONOTIFY        = 0x80
TPM_RETURNCMD       = 0x100

TPM_LEFTBUTTON      = 0x0
TPM_RIGHTBUTTON     = 0x2

TPM_HORNEGANIMATION = 0x800
TPM_HORPOSANIMATION = 0x400
TPM_NOANIMATION     = 0x4000
TPM_VERNEGANIMATION = 0x2000
TPM_VERPOSANIMATION = 0x1000

TrackPopupMenu = ctypes.windll.user32.TrackPopupMenu
TrackPopupMenu.restype = ctypes.wintypes.BOOL
TrackPopupMenu.argtypes = [ctypes.wintypes.HMENU, ctypes.wintypes.UINT, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.wintypes.HWND, ctypes.c_void_p]

PostMessage = ctypes.windll.user32.PostMessageW
PostMessage.restype = ctypes.wintypes.BOOL
PostMessage.argtypes = [ctypes.wintypes.HWND, ctypes.wintypes.UINT, ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM]

DestroyMenu = ctypes.windll.user32.DestroyMenu
DestroyMenu.restype = ctypes.wintypes.BOOL
DestroyMenu.argtypes = [ctypes.wintypes.HMENU]

# Create notification icon

GUID = ctypes.c_ubyte * 16

class TimeoutVersionUnion(ctypes.Union):
    _fields_ = [('uTimeout', ctypes.wintypes.UINT),
                ('uVersion', ctypes.wintypes.UINT),]

NIS_HIDDEN     = 0x1
NIS_SHAREDICON = 0x2

class NOTIFYICONDATA(ctypes.Structure):
    def __init__(self, *args, **kwargs):
        super(NOTIFYICONDATA, self).__init__(*args, **kwargs)
        self.cbSize = ctypes.sizeof(self)
    _fields_ = [
        ('cbSize', ctypes.wintypes.DWORD),
        ('hWnd', ctypes.wintypes.HWND),
        ('uID', ctypes.wintypes.UINT),
        ('uFlags', ctypes.wintypes.UINT),
        ('uCallbackMessage', ctypes.wintypes.UINT),
        ('hIcon', ctypes.wintypes.HICON),
        ('szTip', ctypes.wintypes.WCHAR * 64),
        ('dwState', ctypes.wintypes.DWORD),
        ('dwStateMask', ctypes.wintypes.DWORD),
        ('szInfo', ctypes.wintypes.WCHAR * 256),
        ('union', TimeoutVersionUnion),
        ('szInfoTitle', ctypes.wintypes.WCHAR * 64),
        ('dwInfoFlags', ctypes.wintypes.DWORD),
        ('guidItem', GUID),
        ('hBalloonIcon', ctypes.wintypes.HICON),
    ]

NIM_ADD = 0
NIM_MODIFY = 1
NIM_DELETE = 2
NIM_SETFOCUS = 3
NIM_SETVERSION = 4

NIF_MESSAGE = 1
NIF_ICON = 2
NIF_TIP = 4
NIF_STATE = 8
NIF_INFO = 16
NIF_GUID = 32
NIF_REALTIME = 64
NIF_SHOWTIP = 128

NIIF_NONE = 0
NIIF_INFO = 1
NIIF_WARNING = 2
NIIF_ERROR = 3
NIIF_USER = 4

NOTIFYICON_VERSION = 3
NOTIFYICON_VERSION_4 = 4

Shell_NotifyIcon = ctypes.windll.shell32.Shell_NotifyIconW
Shell_NotifyIcon.restype = ctypes.wintypes.BOOL
Shell_NotifyIcon.argtypes = [ctypes.wintypes.DWORD, ctypes.POINTER(NOTIFYICONDATA)]

# Load icon/image

IMAGE_BITMAP = 0
IMAGE_ICON = 1
IMAGE_CURSOR = 2

LR_CREATEDIBSECTION = 0x00002000
LR_DEFAULTCOLOR     = 0x00000000
LR_DEFAULTSIZE      = 0x00000040
LR_LOADFROMFILE     = 0x00000010
LR_LOADMAP3DCOLORS  = 0x00001000
LR_LOADTRANSPARENT  = 0x00000020
LR_MONOCHROME       = 0x00000001
LR_SHARED           = 0x00008000
LR_VGACOLOR         = 0x00000080

OIC_SAMPLE      = 32512
OIC_HAND        = 32513
OIC_QUES        = 32514
OIC_BANG        = 32515
OIC_NOTE        = 32516
OIC_WINLOGO     = 32517
OIC_WARNING     = OIC_BANG
OIC_ERROR       = OIC_HAND
OIC_INFORMATION = OIC_NOTE

LoadImage = ctypes.windll.user32.LoadImageW
LoadImage.restype = ctypes.wintypes.HANDLE
LoadImage.argtypes = [ctypes.wintypes.HINSTANCE, ctypes.wintypes.LPCWSTR, ctypes.wintypes.UINT, ctypes.c_int, ctypes.c_int, ctypes.wintypes.UINT]

# CreateWindow call

WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.wintypes.HWND, ctypes.c_uint, ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM)
DefWindowProc = ctypes.windll.user32.DefWindowProcW
DefWindowProc.restype = ctypes.c_int
DefWindowProc.argtypes = [ctypes.wintypes.HWND, ctypes.c_uint, ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM]

WS_OVERLAPPED       = 0x00000000L
WS_POPUP            = 0x80000000L
WS_CHILD            = 0x40000000L
WS_MINIMIZE         = 0x20000000L
WS_VISIBLE          = 0x10000000L
WS_DISABLED         = 0x08000000L
WS_CLIPSIBLINGS     = 0x04000000L
WS_CLIPCHILDREN     = 0x02000000L
WS_MAXIMIZE         = 0x01000000L
WS_CAPTION          = 0x00C00000L
WS_BORDER           = 0x00800000L
WS_DLGFRAME         = 0x00400000L
WS_VSCROLL          = 0x00200000L
WS_HSCROLL          = 0x00100000L
WS_SYSMENU          = 0x00080000L
WS_THICKFRAME       = 0x00040000L
WS_GROUP            = 0x00020000L
WS_TABSTOP          = 0x00010000L

WS_MINIMIZEBOX      = 0x00020000L
WS_MAXIMIZEBOX      = 0x00010000L

WS_OVERLAPPEDWINDOW = (WS_OVERLAPPED     |
                       WS_CAPTION        |
                       WS_SYSMENU        |
                       WS_THICKFRAME     |
                       WS_MINIMIZEBOX    |
                       WS_MAXIMIZEBOX)

SM_XVIRTUALSCREEN      = 76
SM_YVIRTUALSCREEN      = 77
SM_CXVIRTUALSCREEN     = 78
SM_CYVIRTUALSCREEN     = 79
SM_CMONITORS           = 80
SM_SAMEDISPLAYFORMAT   = 81

WM_NULL                   = 0x0000
WM_CREATE                 = 0x0001
WM_DESTROY                = 0x0002
WM_MOVE                   = 0x0003
WM_SIZE                   = 0x0005
WM_ACTIVATE               = 0x0006
WM_SETFOCUS               = 0x0007
WM_KILLFOCUS              = 0x0008
WM_ENABLE                 = 0x000A
WM_SETREDRAW              = 0x000B
WM_SETTEXT                = 0x000C
WM_GETTEXT                = 0x000D
WM_GETTEXTLENGTH          = 0x000E
WM_PAINT                  = 0x000F
WM_CLOSE                  = 0x0010
WM_QUERYENDSESSION        = 0x0011
WM_QUIT                   = 0x0012
WM_QUERYOPEN              = 0x0013
WM_ERASEBKGND             = 0x0014
WM_SYSCOLORCHANGE         = 0x0015
WM_ENDSESSION             = 0x0016
WM_SHOWWINDOW             = 0x0018
WM_CTLCOLOR               = 0x0019
WM_WININICHANGE           = 0x001A
WM_SETTINGCHANGE          = 0x001A
WM_DEVMODECHANGE          = 0x001B
WM_ACTIVATEAPP            = 0x001C
WM_FONTCHANGE             = 0x001D
WM_TIMECHANGE             = 0x001E
WM_CANCELMODE             = 0x001F
WM_SETCURSOR              = 0x0020
WM_MOUSEACTIVATE          = 0x0021
WM_CHILDACTIVATE          = 0x0022
WM_QUEUESYNC              = 0x0023
WM_GETMINMAXINFO          = 0x0024
WM_PAINTICON              = 0x0026
WM_ICONERASEBKGND         = 0x0027
WM_NEXTDLGCTL             = 0x0028
WM_SPOOLERSTATUS          = 0x002A
WM_DRAWITEM               = 0x002B
WM_MEASUREITEM            = 0x002C
WM_DELETEITEM             = 0x002D
WM_VKEYTOITEM             = 0x002E
WM_CHARTOITEM             = 0x002F
WM_SETFONT                = 0x0030
WM_GETFONT                = 0x0031
WM_SETHOTKEY              = 0x0032
WM_GETHOTKEY              = 0x0033
WM_QUERYDRAGICON          = 0x0037
WM_COMPAREITEM            = 0x0039
WM_GETOBJECT              = 0x003D
WM_COMPACTING             = 0x0041
WM_COMMNOTIFY             = 0x0044
WM_WINDOWPOSCHANGING      = 0x0046
WM_WINDOWPOSCHANGED       = 0x0047
WM_POWER                  = 0x0048
WM_COPYDATA               = 0x004A
WM_CANCELJOURNAL          = 0x004B
WM_NOTIFY                 = 0x004E
WM_INPUTLANGCHANGEREQUEST = 0x0050
WM_INPUTLANGCHANGE        = 0x0051
WM_TCARD                  = 0x0052
WM_HELP                   = 0x0053
WM_USERCHANGED            = 0x0054
WM_NOTIFYFORMAT           = 0x0055
WM_CONTEXTMENU            = 0x007B
WM_STYLECHANGING          = 0x007C
WM_STYLECHANGED           = 0x007D
WM_DISPLAYCHANGE          = 0x007E
WM_GETICON                = 0x007F
WM_SETICON                = 0x0080
WM_NCCREATE               = 0x0081
WM_NCDESTROY              = 0x0082
WM_NCCALCSIZE             = 0x0083
WM_NCHITTEST              = 0x0084
WM_NCPAINT                = 0x0085
WM_NCACTIVATE             = 0x0086
WM_GETDLGCODE             = 0x0087
WM_SYNCPAINT              = 0x0088
WM_NCMOUSEMOVE            = 0x00A0
WM_NCLBUTTONDOWN          = 0x00A1
WM_NCLBUTTONUP            = 0x00A2
WM_NCLBUTTONDBLCLK        = 0x00A3
WM_NCRBUTTONDOWN          = 0x00A4
WM_NCRBUTTONUP            = 0x00A5
WM_NCRBUTTONDBLCLK        = 0x00A6
WM_NCMBUTTONDOWN          = 0x00A7
WM_NCMBUTTONUP            = 0x00A8
WM_NCMBUTTONDBLCLK        = 0x00A9
WM_KEYDOWN                = 0x0100
WM_KEYUP                  = 0x0101
WM_CHAR                   = 0x0102
WM_DEADCHAR               = 0x0103
WM_SYSKEYDOWN             = 0x0104
WM_SYSKEYUP               = 0x0105
WM_SYSCHAR                = 0x0106
WM_SYSDEADCHAR            = 0x0107
WM_KEYLAST                = 0x0108
WM_IME_STARTCOMPOSITION   = 0x010D
WM_IME_ENDCOMPOSITION     = 0x010E
WM_IME_COMPOSITION        = 0x010F
WM_IME_KEYLAST            = 0x010F
WM_INITDIALOG             = 0x0110
WM_COMMAND                = 0x0111
WM_SYSCOMMAND             = 0x0112
WM_TIMER                  = 0x0113
WM_HSCROLL                = 0x0114
WM_VSCROLL                = 0x0115
WM_INITMENU               = 0x0116
WM_INITMENUPOPUP          = 0x0117
WM_MENUSELECT             = 0x011F
WM_MENUCHAR               = 0x0120
WM_ENTERIDLE              = 0x0121
WM_MENURBUTTONUP          = 0x0122
WM_MENUDRAG               = 0x0123
WM_MENUGETOBJECT          = 0x0124
WM_UNINITMENUPOPUP        = 0x0125
WM_MENUCOMMAND            = 0x0126
WM_CTLCOLORMSGBOX         = 0x0132
WM_CTLCOLOREDIT           = 0x0133
WM_CTLCOLORLISTBOX        = 0x0134
WM_CTLCOLORBTN            = 0x0135
WM_CTLCOLORDLG            = 0x0136
WM_CTLCOLORSCROLLBAR      = 0x0137
WM_CTLCOLORSTATIC         = 0x0138
WM_MOUSEMOVE              = 0x0200
WM_LBUTTONDOWN            = 0x0201
WM_LBUTTONUP              = 0x0202
WM_LBUTTONDBLCLK          = 0x0203
WM_RBUTTONDOWN            = 0x0204
WM_RBUTTONUP              = 0x0205
WM_RBUTTONDBLCLK          = 0x0206
WM_MBUTTONDOWN            = 0x0207
WM_MBUTTONUP              = 0x0208
WM_MBUTTONDBLCLK          = 0x0209
WM_MOUSEWHEEL             = 0x020A
WM_PARENTNOTIFY           = 0x0210
WM_ENTERMENULOOP          = 0x0211
WM_EXITMENULOOP           = 0x0212
WM_NEXTMENU               = 0x0213
WM_SIZING                 = 0x0214
WM_CAPTURECHANGED         = 0x0215
WM_MOVING                 = 0x0216
WM_DEVICECHANGE           = 0x0219
WM_MDICREATE              = 0x0220
WM_MDIDESTROY             = 0x0221
WM_MDIACTIVATE            = 0x0222
WM_MDIRESTORE             = 0x0223
WM_MDINEXT                = 0x0224
WM_MDIMAXIMIZE            = 0x0225
WM_MDITILE                = 0x0226
WM_MDICASCADE             = 0x0227
WM_MDIICONARRANGE         = 0x0228
WM_MDIGETACTIVE           = 0x0229
WM_MDISETMENU             = 0x0230
WM_ENTERSIZEMOVE          = 0x0231
WM_EXITSIZEMOVE           = 0x0232
WM_DROPFILES              = 0x0233
WM_MDIREFRESHMENU         = 0x0234
WM_IME_SETCONTEXT         = 0x0281
WM_IME_NOTIFY             = 0x0282
WM_IME_CONTROL            = 0x0283
WM_IME_COMPOSITIONFULL    = 0x0284
WM_IME_SELECT             = 0x0285
WM_IME_CHAR               = 0x0286
WM_IME_REQUEST            = 0x0288
WM_IME_KEYDOWN            = 0x0290
WM_IME_KEYUP              = 0x0291
WM_MOUSEHOVER             = 0x02A1
WM_MOUSELEAVE             = 0x02A3
WM_CUT                    = 0x0300
WM_COPY                   = 0x0301
WM_PASTE                  = 0x0302
WM_CLEAR                  = 0x0303
WM_UNDO                   = 0x0304
WM_RENDERFORMAT           = 0x0305
WM_RENDERALLFORMATS       = 0x0306
WM_DESTROYCLIPBOARD       = 0x0307
WM_DRAWCLIPBOARD          = 0x0308
WM_PAINTCLIPBOARD         = 0x0309
WM_VSCROLLCLIPBOARD       = 0x030A
WM_SIZECLIPBOARD          = 0x030B
WM_ASKCBFORMATNAME        = 0x030C
WM_CHANGECBCHAIN          = 0x030D
WM_HSCROLLCLIPBOARD       = 0x030E
WM_QUERYNEWPALETTE        = 0x030F
WM_PALETTEISCHANGING      = 0x0310
WM_PALETTECHANGED         = 0x0311
WM_HOTKEY                 = 0x0312
WM_PRINT                  = 0x0317
WM_PRINTCLIENT            = 0x0318
WM_HANDHELDFIRST          = 0x0358
WM_HANDHELDLAST           = 0x035F
WM_AFXFIRST               = 0x0360
WM_AFXLAST                = 0x037F
WM_PENWINFIRST            = 0x0380
WM_PENWINLAST             = 0x038F
WM_APP                    = 0x8000
WM_USER                   = 0x0400
WM_REFLECT                = WM_USER + 0x1c00

class WNDCLASSEX(ctypes.Structure):
    def __init__(self, *args, **kwargs):
        super(WNDCLASSEX, self).__init__(*args, **kwargs)
        self.cbSize = ctypes.sizeof(self)
    _fields_ = [("cbSize", ctypes.c_uint),
                ("style", ctypes.c_uint),
                ("lpfnWndProc", WNDPROC),
                ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int),
                ("hInstance", ctypes.wintypes.HANDLE),
                ("hIcon", ctypes.wintypes.HANDLE),
                ("hCursor", ctypes.wintypes.HANDLE),
                ("hBrush", ctypes.wintypes.HANDLE),
                ("lpszMenuName", ctypes.wintypes.LPCWSTR),
                ("lpszClassName", ctypes.wintypes.LPCWSTR),
                ("hIconSm", ctypes.wintypes.HANDLE)]

ShowWindow = ctypes.windll.user32.ShowWindow
ShowWindow.argtypes = [ctypes.wintypes.HWND, ctypes.c_int]

def GenerateDummyWindow(callback, uid):
    newclass = WNDCLASSEX()
    newclass.lpfnWndProc = callback
    newclass.lpszClassName = uid.replace("-", "")
    ATOM = ctypes.windll.user32.RegisterClassExW(ctypes.byref(newclass))
    hwnd = ctypes.windll.user32.CreateWindowExW(0, newclass.lpszClassName, None, WS_POPUP, 0, 0, 0, 0, 0, 0, 0, 0)
    return hwnd

# Message loop calls

TIMERCALLBACK = ctypes.WINFUNCTYPE(None,
                                   ctypes.wintypes.HWND,
                                   ctypes.wintypes.UINT,
                                   ctypes.POINTER(ctypes.wintypes.UINT),
                                   ctypes.wintypes.DWORD)

SetTimer = ctypes.windll.user32.SetTimer
SetTimer.restype = ctypes.POINTER(ctypes.wintypes.UINT)
SetTimer.argtypes = [ctypes.wintypes.HWND,
                     ctypes.POINTER(ctypes.wintypes.UINT),
                     ctypes.wintypes.UINT,
                     TIMERCALLBACK]

KillTimer = ctypes.windll.user32.KillTimer
KillTimer.restype = ctypes.wintypes.BOOL
KillTimer.argtypes = [ctypes.wintypes.HWND,
                      ctypes.POINTER(ctypes.wintypes.UINT)]

class MSG(ctypes.Structure):
    _fields_ = [ ('HWND', ctypes.wintypes.HWND),
                 ('message', ctypes.wintypes.UINT),
                 ('wParam', ctypes.wintypes.WPARAM),
                 ('lParam', ctypes.wintypes.LPARAM),
                 ('time', ctypes.wintypes.DWORD),
                 ('pt', POINT)]

GetMessage = ctypes.windll.user32.GetMessageW
GetMessage.restype = ctypes.wintypes.BOOL
GetMessage.argtypes = [ctypes.POINTER(MSG), ctypes.wintypes.HWND, ctypes.wintypes.UINT, ctypes.wintypes.UINT]

TranslateMessage = ctypes.windll.user32.TranslateMessage
TranslateMessage.restype = ctypes.wintypes.ULONG
TranslateMessage.argtypes = [ctypes.POINTER(MSG)]

DispatchMessage = ctypes.windll.user32.DispatchMessageW
DispatchMessage.restype = ctypes.wintypes.ULONG
DispatchMessage.argtypes = [ctypes.POINTER(MSG)]

def LoadIcon(iconfilename, small=False):
        return LoadImage(0,
                         unicode(iconfilename),
                         IMAGE_ICON,
                         16 if small else 0,
                         16 if small else 0,
                         LR_LOADFROMFILE)


class NotificationIcon(object):
    def __init__(self, iconfilename, tooltip=None):
        assert os.path.isfile(unicode(iconfilename)), "{} doesn't exist".format(iconfilename)
        self._iconfile = unicode(iconfilename)
        self._hicon = LoadIcon(self._iconfile, True)
        assert self._hicon, "Failed to load {}".format(iconfilename)
        #self._pumpqueue = Queue.Queue()
        self._die = False
        self._timerid = None
        self._uid = uuid.uuid4()
        self._tooltip = unicode(tooltip) if tooltip else u''
        #self._thread = threading.Thread(target=self._run)
        #self._thread.start()
        self._info_bubble = None
        self.items = []


    def _bubble(self, iconinfo):
        if self._info_bubble:
            info_bubble = self._info_bubble
            self._info_bubble = None
            message = unicode(self._info_bubble)
            iconinfo.uFlags |= NIF_INFO
            iconinfo.szInfo = message
            iconinfo.szInfoTitle = message
            iconinfo.dwInfoFlags = NIIF_INFO
            iconinfo.union.uTimeout = 10000
            Shell_NotifyIcon(NIM_MODIFY, ctypes.pointer(iconinfo))


    def _run(self):
        self.WM_TASKBARCREATED = ctypes.windll.user32.RegisterWindowMessageW(u'TaskbarCreated')

        self._windowproc = WNDPROC(self._callback)
        self._hwnd = GenerateDummyWindow(self._windowproc, str(self._uid))

        iconinfo = NOTIFYICONDATA()
        iconinfo.hWnd = self._hwnd
        iconinfo.uID = 100
        iconinfo.uFlags = NIF_ICON | NIF_SHOWTIP | NIF_MESSAGE | (NIF_TIP if self._tooltip else 0)
        iconinfo.uCallbackMessage = WM_MENUCOMMAND
        iconinfo.hIcon = self._hicon
        iconinfo.szTip = self._tooltip

        Shell_NotifyIcon(NIM_ADD, ctypes.pointer(iconinfo))

        self.iconinfo = iconinfo

        PostMessage(self._hwnd, WM_NULL, 0, 0)

        message = MSG()
        last_time = -1
        ret = None
        while not self._die:
            try:
                ret = GetMessage(ctypes.pointer(message), 0, 0, 0)
                TranslateMessage(ctypes.pointer(message))
                DispatchMessage(ctypes.pointer(message))
            except Exception, err:
                # print "NotificationIcon error", err, message
                message = MSG()
            time.sleep(0.125)
        print "Icon thread stopped, removing icon..."

        Shell_NotifyIcon(NIM_DELETE, ctypes.cast(ctypes.pointer(iconinfo), ctypes.POINTER(NOTIFYICONDATA)))
        ctypes.windll.user32.DestroyWindow(self._hwnd)
        ctypes.windll.user32.DestroyIcon(self._hicon)


    def _menu(self):
        if not hasattr(self, 'items'):
            return

        menu = CreatePopupMenu()
        func = None

        try:
            iidx = 1000
            defaultitem = -1
            item_map = {}
            for fs in self.items:
                iidx += 1
                if isinstance(fs, basestring):
                    if fs and not fs.strip('-_='):
                        AppendMenu(menu, MF_SEPARATOR, iidx, fs)
                    else:
                        AppendMenu(menu, MF_STRING | MF_GRAYED, iidx, fs)
                elif isinstance(fs, tuple):
                    if callable(fs[0]):
                        itemstring = fs[0]()
                    else:
                        itemstring = unicode(fs[0])
                    flags = MF_STRING
                    if itemstring.startswith("!"):
                        itemstring = itemstring[1:]
                        defaultitem = iidx
                    if itemstring.startswith("+"):
                        itemstring = itemstring[1:]
                        flags = flags | MF_CHECKED
                    itemcallable = fs[1]
                    item_map[iidx] = itemcallable
                    if itemcallable is False:
                        flags = flags | MF_DISABLED
                    elif not callable(itemcallable):
                        flags = flags | MF_GRAYED
                    AppendMenu(menu, flags, iidx, itemstring)

            if defaultitem != -1:
                SetMenuDefaultItem(menu, defaultitem, 0)

            pos = POINT()
            GetCursorPos(ctypes.pointer(pos))

            PostMessage(self._hwnd, WM_NULL, 0, 0)

            SetForegroundWindow(self._hwnd)

            ti = TrackPopupMenu(menu, TPM_RIGHTBUTTON | TPM_RETURNCMD | TPM_NONOTIFY, pos.x, pos.y, 0, self._hwnd, None)

            if ti in item_map:
                func = item_map[ti]

            PostMessage(self._hwnd, WM_NULL, 0, 0)
        finally:
            DestroyMenu(menu)
        if func: func()


    def clicked(self):
        self._menu()



    def _callback(self, hWnd, msg, wParam, lParam):
        # Check if the main thread is still alive
        if msg == WM_TIMER:
            if not any(thread.getName() == 'MainThread' and thread.isAlive()
                       for thread in threading.enumerate()):
                self._die = True
        elif msg == WM_MENUCOMMAND and lParam == WM_LBUTTONUP:
            self.clicked()
        elif msg == WM_MENUCOMMAND and lParam == WM_RBUTTONUP:
            self._menu()
        elif msg == self.WM_TASKBARCREATED: # Explorer restarted, add the icon again.
            Shell_NotifyIcon(NIM_ADD, ctypes.pointer(self.iconinfo))
        else:
            return DefWindowProc(hWnd, msg, wParam, lParam)
        return 1


    def die(self):
        self._die = True
        PostMessage(self._hwnd, WM_NULL, 0, 0)
        time.sleep(0.2)
        try:
            Shell_NotifyIcon(NIM_DELETE, self.iconinfo)
        except Exception, err:
            print "Icon remove error", err
        ctypes.windll.user32.DestroyWindow(self._hwnd)
        ctypes.windll.user32.DestroyIcon(self._hicon)


    def pump(self):
        try:
            while not self._pumpqueue.empty():
                callable = self._pumpqueue.get(False)
                callable()
        except Queue.Empty:
            pass


    def announce(self, text):
        self._info_bubble = text


def hideConsole():
    ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)

def showConsole():
    ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 1)

def hasConsole():
    return ctypes.windll.kernel32.GetConsoleWindow() != 0

if __name__ == "__main__":
    import time

    def greet():
        ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
        print "Hello"

    def quit():
        ni._die = True

    def announce():
        ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 1)
        ni.announce("Hello there")

    def clicked():
        ni.announce("Hello")

    def dynamicTitle():
        return "!The time is: %s" % time.time()

    ni = NotificationIcon(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../trayicon.ico'), "ZeroNet 0.2.9")
    ni.items = [
        (dynamicTitle, False),
        ('Hello', greet),
        ('Title', False),
        ('!Default', greet),
        ('+Popup bubble', announce),
        'Nothing',
        '--',
        ('Quit', quit)
    ]
    ni.clicked = clicked
    import atexit

    @atexit.register
    def goodbye():
        print "You are now leaving the Python sector."

    ni._run()