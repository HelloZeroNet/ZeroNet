#!/usr/bin/env python
# -*- coding: utf-8 -*-#
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
import json
import threading

# OSX AppKit Path
current_path = os.path.dirname(os.path.abspath(__file__))
python_path = os.path.abspath( os.path.join(current_path, os.pardir, os.pardir, 'python27', '1.0'))

osx_lib = os.path.join(python_path, 'lib', 'darwin')
sys.path.append(osx_lib)
extra_lib = "/System/Library/Frameworks/Python.framework/Versions/2.7/Extras/lib/python/PyObjC"
sys.path.append(extra_lib)

from PyObjCTools import AppHelper
from AppKit import NSObject, NSApp, NSApplication, NSWorkspace, NSStatusBar, NSMenu, NSMenuItem, NSImage,NSApplicationActivationPolicyProhibited , NSWorkspaceWillPowerOffNotification, NSVariableStatusItemLength

global MENU_ITEMS, INFO
MENU_ITEMS = dict()
INFO = dict({
    'homepage': 'http://127.0.0.1:43110/1HeLLo4uzjaLetFx6NH3PMwFP3qbRbTf3D',
    'ip_external': '127.0.0.1'
})

class MacTrayObject(NSObject):
    def message(self,action, args=None):
        print 'message %s %s' % (action , (args or ''))
        sys.stdout.flush()

    def applicationDidFinishLaunching_(self, notification):
        self.setupUI()
        self.registerObserver()

    def create_menu_item(self, key, title , callback ):
        it = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_( title , callback , '')
        self.menu.addItem_( it )
        MENU_ITEMS[ key ] = it

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

        #self.create_menu_item( 'ip_external', 'IP: %s' % INFO['ip_external'],  'info:')
        self.menu.addItem_( NSMenuItem.separatorItem() )

        # Links
        self.create_menu_item( 'open_zeronet', 'Open ZeroNet',  'open:')
        self.create_menu_item( 'open_reddit', 'Zeronet Reddot', 'openreddit:')
        self.create_menu_item( 'open_gh', 'Report issues/feature requests', 'opengithub:')

        self.menu.addItem_( NSMenuItem.separatorItem() )

        self.create_menu_item( 'quit_zeronet', 'Quit ZeroNet', 'windowWillClose:' )

        # Bind it to the status item and hide dock icon
        self.statusitem.setMenu_(self.menu)
        NSApp.setActivationPolicy_(NSApplicationActivationPolicyProhibited)

    def registerObserver(self):
        nc = NSWorkspace.sharedWorkspace().notificationCenter()
        nc.addObserver_selector_name_object_(self, 'windowWillClose:', NSWorkspaceWillPowerOffNotification, None)

    def windowWillClose_(self, notification):
        self.message('quit')
        NSApp.terminate_(self)

    def open_(self, notification):
        self.message('open')
        webbrowser.open_new( INFO['homepage'] )

    def openreddit_(self):
        webbrowser.open_new("https://www.reddit.com/r/zeronet")
        self.message('open','reddit')

    def opengithub_(self):
        webbrowser.open_new("https://github.com/HelloZeroNet/ZeroNet")
        self.message('open','github')

    def info_(self, notification):
        pass

    def set(self, key, value):
        self.update_title_items()
        self.message('ok')

def tray_init():
    global tray_app, app_delegate
    tray_app = NSApplication.sharedApplication()
    app_delegate = MacTrayObject.alloc().init()
    tray_app.setDelegate_(app_delegate)

def tray_run():
    AppHelper.runEventLoop()

if __name__ == '__main__':
    if(len(sys.argv) > 2):
        INFO['homepage'] = sys.argv[1]
        INFO['ip_external'] = sys.argv[2]

    tray_init()
    tray_run()
