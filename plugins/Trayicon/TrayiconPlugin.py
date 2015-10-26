import time
import os
import sys
import atexit

from Plugin import PluginManager
from Config import config

allow_reload = False  # No source reload supported in this plugin


@PluginManager.registerTo("Actions")
class ActionsPlugin(object):

    def main(self):
        global notificationicon, winfolders
        from lib import notificationicon, winfolders
        import gevent.threadpool

        self.main = sys.modules["main"]

        fs_encoding = sys.getfilesystemencoding()

        icon = notificationicon.NotificationIcon(
            os.path.join(os.path.dirname(os.path.abspath(__file__).decode(fs_encoding)), 'trayicon.ico'),
            "ZeroNet %s" % config.version
        )
        self.icon = icon

        if not config.debug:  # Hide console if not in debug mode
            notificationicon.hideConsole()
            self.console = False
        else:
            self.console = True

        @atexit.register
        def hideIcon():
            icon.die()

        ui_ip = config.ui_ip if config.ui_ip != "*" else "127.0.0.1"

        icon.items = (
            (self.titleIp, False),
            (self.titleConnections, False),
            (self.titleTransfer, False),
            (self.titleConsole, self.toggleConsole),
            (self.titleAutorun, self.toggleAutorun),
            "--",
            ("ZeroNet Twitter", lambda: self.opensite("https://twitter.com/HelloZeroNet")),
            ("ZeroNet Reddit", lambda: self.opensite("http://www.reddit.com/r/zeronet/")),
            ("ZeroNet Github", lambda: self.opensite("https://github.com/HelloZeroNet/ZeroNet")),
            ("Report bug/request feature", lambda: self.opensite("https://github.com/HelloZeroNet/ZeroNet/issues")),
            "--",
            ("!Open ZeroNet", lambda: self.opensite("http://%s:%s" % (ui_ip, config.ui_port))),
            "--",
            ("Quit", self.quit),

        )

        icon.clicked = lambda: self.opensite("http://%s:%s" % (ui_ip, config.ui_port))
        gevent.threadpool.start_new_thread(icon._run, ())  # Start in real thread (not gevent compatible)
        super(ActionsPlugin, self).main()
        icon._die = True

    def quit(self):
        self.icon.die()
        time.sleep(0.1)
        sys.exit()
        # self.main.ui_server.stop()
        # self.main.file_server.stop()

    def opensite(self, url):
        import webbrowser
        webbrowser.open(url, new=0)

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

    def titleConsole(self):
        if self.console:
            return "+Show console window"
        else:
            return "Show console window"

    def toggleConsole(self):
        if self.console:
            notificationicon.hideConsole()
            self.console = False
        else:
            notificationicon.showConsole()
            self.console = True

    def getAutorunPath(self):
        return "%s\\zeronet.cmd" % winfolders.get(winfolders.STARTUP)

    def formatAutorun(self):
        args = sys.argv[:]
        args.insert(0, sys.executable)
        if sys.platform == 'win32':
            args = ['"%s"' % arg for arg in args]
        cmd = " ".join(args)

        # Dont open browser on autorun
        cmd = cmd.replace("start.py", "zeronet.py").replace('"--open_browser"', "").replace('"default_browser"', "").strip()

        return "@echo off\ncd /D %s\n%s" % (os.getcwd(), cmd)

    def isAutorunEnabled(self):
        path = self.getAutorunPath()
        return os.path.isfile(path) and open(path).read() == self.formatAutorun()

    def titleAutorun(self):
        if self.isAutorunEnabled():
            return "+Start ZeroNet when Windows starts"
        else:
            return "Start ZeroNet when Windows starts"

    def toggleAutorun(self):
        if self.isAutorunEnabled():
            os.unlink(self.getAutorunPath())
        else:
            open(self.getAutorunPath(), "w").write(self.formatAutorun())
