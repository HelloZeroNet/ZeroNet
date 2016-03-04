import time
import os
import sys
import atexit
import webbrowser
import logging

from threading import Thread

from Plugin import PluginManager
from Config import config

allow_reload = False  # No source reload supported in this plugin
current_path = os.path.dirname(os.path.abspath(__file__))

log = logging.getLogger("ZeronamePlugin")


def tray_threaded( plugin_action ):
    """
        Tray in another process
        Thread to comunicate from<->to tray
    """
    global tray

    # Launch tray process
    from subprocess import Popen, PIPE
    from threading import Thread

    tray_osx = "%s/lib/tray_osx.py" % (current_path )
    tray = Popen( tray_osx , shell=True, stdin=PIPE, stdout=PIPE )

    # Read data from tray process
    while True:
        output = non_block_read( tray.stdout ).split(' ')
        # Dispatch actions
        if(output[0] == 'dispatch'):
            action = output[1][:-1]

            try:
                app_method = getattr(plugin_action, action)
                app_method()
            except Exception, e:
                print "Unknown action from trayIcon: %s" % action

        time.sleep(1)

@PluginManager.registerTo("Actions")
class ActionsPlugin(object):

    def main(self):
        import gevent.threadpool
        global tray_thread , main

        main = sys.modules["main"]
        fs_encoding = sys.getfilesystemencoding()

        tray_thread = gevent.threadpool.start_new_thread( tray_threaded, (self,))
        super(ActionsPlugin, self).main()

    @atexit.register
    def quitTrayIcon():
        tray.terminate()

    def quit(self):
        tray.terminate()
        sys.exit()

    def start(self):
        print "start"
        print main.file_server.connections

    def open(self):
        webbrowser.open_new("http://%s:%s/%s" % ( config.ui_ip, config.ui_port, config.homepage ) )


    def titleIp(self):
        title = "!IP: %s" % config.ip_external
        if main.file_server.port_opened:
            title += " (active)"
        else:
            title += " (passive)"
        return title

    def titleConnections(self):
        title = "Connections: %s" % len(main.file_server.connections)
        return title

    def titleTransfer(self):
        title = "Received: %.2f MB | Sent: %.2f MB" % (
            float(self.main.file_server.bytes_recv) / 1024 / 1024,
            float(self.main.file_server.bytes_sent) / 1024 / 1024
        )
        return title


import fcntl
def non_block_read(output):
    ''' read without blocking '''
    fd = output.fileno()
    fl = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
    try:
        return output.read()
    except:
        return ''
