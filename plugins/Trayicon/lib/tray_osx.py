#!/usr/bin/env python
#
#
# This is a standalone script to create a TrayIcon on OSX.
# It's run as a standalone, because AppKit cannot run on
# any way in gevent/threads.
#
#

import time
import os
import sys
import atexit
import webbrowser

# OSX AppKit Path
current_path = os.path.dirname(os.path.abspath(__file__))
python_path = os.path.abspath( os.path.join(current_path, os.pardir, os.pardir, 'python27', '1.0'))

osx_lib = os.path.join(python_path, 'lib', 'darwin')
sys.path.append(osx_lib)
extra_lib = "/System/Library/Frameworks/Python.framework/Versions/2.7/Extras/lib/python/PyObjC"
sys.path.append(extra_lib)

from PyObjCTools import AppHelper
from AppKit import *


class MacTrayObject(NSObject):
    """ Taken from XX-NET """
    def __init__(self):
        print "MacTray Called"

    def set_info_items(self, items):
        self.menu_info_items = items

    def applicationDidFinishLaunching_(self, notification):
        self.setupUI()

        print 'dispatch start'
        sys.stdout.flush()

        self.registerObserver()


    def setupUI(self):
        self.statusbar = NSStatusBar.systemStatusBar()
        self.statusitem = self.statusbar.statusItemWithLength_(NSVariableStatusItemLength) #NSSquareStatusItemLength #NSVariableStatusItemLength

        # Set initial image icon
        icon_path = os.path.join(current_path, "../trayicon.ico")
        image = NSImage.alloc().initByReferencingFile_(icon_path)
        image.setScalesWhenResized_(True)
        image.setSize_((20, 20))
        self.statusitem.setImage_(image)

        # Let it highlight upon clicking
        self.statusitem.setHighlightMode_(1)
        self.statusitem.setToolTip_("ZeroNet")

        # Build a very simple menu
        self.menu = NSMenu.alloc().init()
        self.menu.setAutoenablesItems_(False)

        # Create info items
        """
        for item in self.menu_info_items:
            menuitem = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_( item, 'info:','')
            self.menu.addItem( menuItem )
        """

        # Other items
        menuitem = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_('Open ZeroNet', 'open:', '')
        self.menu.addItem_(menuitem)

        # Default event
        menuitem = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_('Quit', 'windowWillClose:', '')
        self.menu.addItem_(menuitem)

        # Bind it to the status item
        self.statusitem.setMenu_(self.menu)

        # Hide dock icon
        NSApp.setActivationPolicy_(NSApplicationActivationPolicyProhibited)

    def registerObserver(self):
        nc = NSWorkspace.sharedWorkspace().notificationCenter()
        nc.addObserver_selector_name_object_(self, 'windowWillClose:', NSWorkspaceWillPowerOffNotification, None)

    def windowWillClose_(self, notification):
        print 'dispatch quit'
        sys.stdout.flush()
        NSApp.terminate_(self)

    def setParams(self, ui_ip , ui_port, homepage ):
        self.config = {
            'ui_ip': ui_ip,
            'ui_port': ui_port,
            'homepage': homepage
        }

    def open_(self, notification):
        print 'dispatch open'
        sys.stdout.flush()

    #Note: the function name for action can include '_'
    # limited by Mac cocoa
    def resetGoagent_(self, _):
        print 'goagent stop'
        print 'goagent start'

    def enableProxy_(self, _):
        print 'enable proxy'

    def disableProxy_(self, _):
        print 'disable proxy'


def tray_init():
    global tray_app, delegate
    tray_app = NSApplication.sharedApplication()
    delegate = MacTrayObject.alloc().init()

    #delegate.setParams( *sys.argv[1:] )

def tray_run():
    global tray_app, delegate
    tray_app.setDelegate_(delegate)
    AppHelper.runEventLoop()

if __name__ == '__main__':
    tray_init()
    tray_run()
