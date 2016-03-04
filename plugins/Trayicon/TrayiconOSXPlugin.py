import time
import os
import sys
import atexit
import webbrowser

from Plugin import PluginManager
from Config import config

allow_reload = False  # No source reload supported in this plugin
current_path = os.path.dirname(os.path.abspath(__file__))

@PluginManager.registerTo("Actions")
class ActionsPlugin(object):

    def main(self):
        import gevent.threadpool , gevent.thread
        global tray_app

        self.main = sys.modules["main"]
        fs_encoding = sys.getfilesystemencoding()

        config.ui_ip = config.ui_ip if config.ui_ip != "*" else "127.0.0.1"
        #info_items = [ self.titleIp, self.titleConnections,
        #               self.titleTransfer ]


        import subprocess
        status = subprocess.call(
            "python %s/lib/tray_osx.py %s %s %s" % ( current_path ,
                *[config.ui_ip, config.ui_port, config.homepage] ),
            shell=True)
        print status

        super(ActionsPlugin, self).main()


    def titleIp(self):
        title = "!IP: %s" % config.ip_external
        if self.main.file_server.port_opened:
            title += " (active)"
        else:
            title += " (passive)"
        return title

    def titleConnections(self):
        title = "Connections: %s" % len(self.main.file_server.connections)
        return title

    def titleTransfer(self):
        title = "Received: %.2f MB | Sent: %.2f MB" % (
            float(self.main.file_server.bytes_recv) / 1024 / 1024,
            float(self.main.file_server.bytes_sent) / 1024 / 1024
        )
        return title
