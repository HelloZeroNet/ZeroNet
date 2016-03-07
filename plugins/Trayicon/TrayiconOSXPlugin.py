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

log = logging.getLogger("plugins-trayicon")

def tray_read():
    global tray_thread, main, tray, plugin

    while True:
        _in = tray.stdout.readline()
        (message, action , args ) = _in[:-1].split(' ')
        if(action == 'quit'):
            plugin.quit()

        time.sleep(1)

@PluginManager.registerTo("Actions")
class ActionsPlugin(object):

    def main(self):
        import gevent.threadpool
        global tray_thread, main, tray , plugin

        main = sys.modules["main"]
        fs_encoding = sys.getfilesystemencoding()

        # Launch tray process
        from subprocess import Popen, PIPE
        from threading import Thread

        tray_osx_app = "%s/lib/tray_osx.py %s %s" % (current_path , self.homepage() , self.titleIp())
        tray = Popen( tray_osx_app , shell=True , stdout=PIPE, stdin=PIPE)

        # Read messages from tray app
        plugin = self
        tray_thread = gevent.threadpool.start_new_thread( tray_read , ())

        super(ActionsPlugin, self).main()

    @atexit.register
    def quitTrayIcon():
        tray.terminate()

    def quit(self):
        tray.terminate()
        os._exit(0)

    def homepage(self):
        ui_ip = config.ui_ip if config.ui_ip != "*" else "127.0.0.1"
        return "http://%s:%s/%s" % (ui_ip, config.ui_port, config.homepage)

    def titleIp(self):
        title = "%s" % (config.ip_external or '127.0.0.1')
        return title

    def transfer(self):
        def bytes_to_mb(b):
            return '%.2fMB' % (float(b) / 1024 / 1024)

        return {'recv': bytes_to_mb(self.main.file_server.bytes_recv),
                'sent': bytes_to_mb(self.main.file_server.bytes_sent)}
