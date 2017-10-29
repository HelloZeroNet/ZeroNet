import os
import sys
import atexit

from Plugin import PluginManager
from Config import config
from Translate import Translate

allow_reload = False  # No source reload supported in this plugin

if "_" not in locals():
    _ = Translate("plugins/Trayicon/languages/")


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

        icon.items = [
            (self.titleIp, False),
            (self.titleConnections, False),
            (self.titleTransfer, False),
            (self.titleConsole, self.toggleConsole),
            (self.titleAutorun, self.toggleAutorun),
            "--",
            (_["ZeroNet Twitter"], lambda: self.opensite("https://twitter.com/HelloZeroNet")),
            (_["ZeroNet Reddit"], lambda: self.opensite("http://www.reddit.com/r/zeronet/")),
            (_["ZeroNet Github"], lambda: self.opensite("https://github.com/HelloZeroNet/ZeroNet")),
            (_["Report bug/request feature"], lambda: self.opensite("https://github.com/HelloZeroNet/ZeroNet/issues")),
            "--",
            (_["!Open ZeroNet"], lambda: self.opensite("http://%s:%s/%s" % (ui_ip, config.ui_port, config.homepage))),
            "--",
            (_["Quit"], self.quit),
        ]

        if not notificationicon.hasConsole():
            del icon.items[3]

        icon.clicked = lambda: self.opensite("http://%s:%s/%s" % (ui_ip, config.ui_port, config.homepage))
        self.quit_servers_event = gevent.threadpool.ThreadResult(
            lambda res: gevent.spawn_later(0.1, self.quitServers)
        )  # Fix gevent thread switch error
        gevent.threadpool.start_new_thread(icon._run, ())  # Start in real thread (not gevent compatible)
        super(ActionsPlugin, self).main()
        icon._die = True

    def quit(self):
        self.icon.die()
        self.quit_servers_event.set(True)

    def quitServers(self):
        self.main.ui_server.stop()
        self.main.file_server.stop()

    def opensite(self, url):
        import webbrowser
        webbrowser.open(url, new=0)

    def titleIp(self):
        title = "!IP: %s " % config.ip_external
        if self.main.file_server.port_opened:
            title += _["(active)"]
        else:
            title += _["(passive)"]
        return title

    def titleConnections(self):
        title = _["Connections: %s"] % len(self.main.file_server.connections)
        return title

    def titleTransfer(self):
        title = _["Received: %.2f MB | Sent: %.2f MB"] % (
            float(self.main.file_server.bytes_recv) / 1024 / 1024,
            float(self.main.file_server.bytes_sent) / 1024 / 1024
        )
        return title

    def titleConsole(self):
        translate = _["Show console window"]
        if self.console:
            return "+" + translate
        else:
            return translate

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

        if not getattr(sys, 'frozen', False):  # Not frozen
            args.insert(0, sys.executable)
            cwd = os.getcwd().decode(sys.getfilesystemencoding())
        else:
            cwd = os.path.dirname(sys.executable).decode(sys.getfilesystemencoding())

        if sys.platform == 'win32':
            args = ['"%s"' % arg for arg in args if arg]
        cmd = " ".join(args)

        # Dont open browser on autorun
        cmd = cmd.replace("start.py", "zeronet.py").replace('"--open_browser"', "").replace('"default_browser"', "").strip()
        cmd += ' --open_browser ""'
        cmd = cmd.decode(sys.getfilesystemencoding())

        return u"""
            @echo off
            chcp 65001 > nul
            set PYTHONIOENCODING=utf-8
            cd /D \"%s\"
            start "" %s
        """ % (cwd, cmd)

    def isAutorunEnabled(self):
        path = self.getAutorunPath()
        return os.path.isfile(path) and open(path).read().decode("utf8") == self.formatAutorun()

    def titleAutorun(self):
        translate = _["Start ZeroNet when Windows starts"]
        if self.isAutorunEnabled():
            return "+" + translate
        else:
            return translate

    def toggleAutorun(self):
        if self.isAutorunEnabled():
            os.unlink(self.getAutorunPath())
        else:
            open(self.getAutorunPath(), "w").write(self.formatAutorun().encode("utf8"))
