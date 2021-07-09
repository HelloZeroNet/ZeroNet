import time
import html
import os
import json
import sys
import itertools

from Plugin import PluginManager
from Config import config
from util import helper
from Debug import Debug
from Db import Db


@PluginManager.registerTo("UiRequest")
class UiRequestPlugin(object):

    def formatTableRow(self, row, class_name=""):
        back = []
        for format, val in row:
            if val is None:
                formatted = "n/a"
            elif format == "since":
                if val:
                    formatted = "%.0f" % (time.time() - val)
                else:
                    formatted = "n/a"
            else:
                formatted = format % val
            back.append("<td>%s</td>" % formatted)
        return "<tr class='%s'>%s</tr>" % (class_name, "".join(back))

    def getObjSize(self, obj, hpy=None):
        if hpy:
            return float(hpy.iso(obj).domisize) / 1024
        else:
            return 0

    def renderHead(self):
        import main
        from Crypt import CryptConnection

        # Memory
        yield "rev%s | " % config.rev
        yield "%s | " % main.file_server.ip_external_list
        yield "Port: %s | " % main.file_server.port
        yield "Network: %s | " % main.file_server.supported_ip_types
        yield "Opened: %s | " % main.file_server.port_opened
        yield "Crypt: %s, TLSv1.3: %s | " % (CryptConnection.manager.crypt_supported, CryptConnection.ssl.HAS_TLSv1_3)
        yield "In: %.2fMB, Out: %.2fMB  | " % (
            float(main.file_server.bytes_recv) / 1024 / 1024,
            float(main.file_server.bytes_sent) / 1024 / 1024
        )
        yield "Peerid: %s  | " % main.file_server.peer_id
        yield "Time: %.2fs | " % main.file_server.getTimecorrection()
        yield "Blocks: %s" % Debug.num_block

        try:
            import psutil
            process = psutil.Process(os.getpid())
            mem = process.get_memory_info()[0] / float(2 ** 20)
            yield "Mem: %.2fMB | " % mem
            yield "Threads: %s | " % len(process.threads())
            yield "CPU: usr %.2fs sys %.2fs | " % process.cpu_times()
            yield "Files: %s | " % len(process.open_files())
            yield "Sockets: %s | " % len(process.connections())
            yield "Calc size <a href='?size=1'>on</a> <a href='?size=0'>off</a>"
        except Exception:
            pass
        yield "<br>"

    def renderConnectionsTable(self):
        import main

        # Connections
        yield "<b>Connections</b> (%s, total made: %s, in: %s, out: %s):<br>" % (
            len(main.file_server.connections), main.file_server.last_connection_id,
            main.file_server.num_incoming, main.file_server.num_outgoing
        )
        yield "<table class='connections'><tr> <th>id</th> <th>type</th> <th>ip</th> <th>open</th> <th>crypt</th> <th>ping</th>"
        yield "<th>buff</th> <th>bad</th> <th>idle</th> <th>open</th> <th>delay</th> <th>cpu</th> <th>out</th> <th>in</th> <th>last sent</th>"
        yield "<th>wait</th> <th>version</th> <th>time</th> <th>sites</th> </tr>"
        for connection in main.file_server.connections:
            if "cipher" in dir(connection.sock):
                cipher = connection.sock.cipher()[0]
                tls_version = connection.sock.version()
            else:
                cipher = connection.crypt
                tls_version = ""
            if "time" in connection.handshake and connection.last_ping_delay:
                time_correction = connection.handshake["time"] - connection.handshake_time - connection.last_ping_delay
            else:
                time_correction = 0.0
            yield self.formatTableRow([
                ("%3d", connection.id),
                ("%s", connection.type),
                ("%s:%s", (connection.ip, connection.port)),
                ("%s", connection.handshake.get("port_opened")),
                ("<span title='%s %s'>%s</span>", (cipher, tls_version, connection.crypt)),
                ("%6.3f", connection.last_ping_delay),
                ("%s", connection.incomplete_buff_recv),
                ("%s", connection.bad_actions),
                ("since", max(connection.last_send_time, connection.last_recv_time)),
                ("since", connection.start_time),
                ("%.3f", max(-1, connection.last_sent_time - connection.last_send_time)),
                ("%.3f", connection.cpu_time),
                ("%.0fk", connection.bytes_sent / 1024),
                ("%.0fk", connection.bytes_recv / 1024),
                ("<span title='Recv: %s'>%s</span>", (connection.last_cmd_recv, connection.last_cmd_sent)),
                ("%s", list(connection.waiting_requests.keys())),
                ("%s r%s", (connection.handshake.get("version"), connection.handshake.get("rev", "?"))),
                ("%.2fs", time_correction),
                ("%s", connection.sites)
            ])
        yield "</table>"

    def renderTrackers(self):
        # Trackers
        yield "<br><br><b>Trackers:</b><br>"
        yield "<table class='trackers'><tr> <th>address</th> <th>request</th> <th>successive errors</th> <th>last_request</th></tr>"
        from Site import SiteAnnouncer  # importing at the top of the file breaks plugins
        for tracker_address, tracker_stat in sorted(SiteAnnouncer.global_stats.items()):
            yield self.formatTableRow([
                ("%s", tracker_address),
                ("%s", tracker_stat["num_request"]),
                ("%s", tracker_stat["num_error"]),
                ("%.0f min ago", min(999, (time.time() - tracker_stat["time_request"]) / 60))
            ])
        yield "</table>"

        if "AnnounceShare" in PluginManager.plugin_manager.plugin_names:
            yield "<br><br><b>Shared trackers:</b><br>"
            yield "<table class='trackers'><tr> <th>address</th> <th>added</th> <th>found</th> <th>latency</th> <th>successive errors</th> <th>last_success</th></tr>"
            from AnnounceShare import AnnounceSharePlugin
            for tracker_address, tracker_stat in sorted(AnnounceSharePlugin.tracker_storage.getTrackers().items()):
                yield self.formatTableRow([
                    ("%s", tracker_address),
                    ("%.0f min ago", min(999, (time.time() - tracker_stat["time_added"]) / 60)),
                    ("%.0f min ago", min(999, (time.time() - tracker_stat.get("time_found", 0)) / 60)),
                    ("%.3fs", tracker_stat["latency"]),
                    ("%s", tracker_stat["num_error"]),
                    ("%.0f min ago", min(999, (time.time() - tracker_stat["time_success"]) / 60)),
                ])
            yield "</table>"

    def renderTor(self):
        import main
        yield "<br><br><b>Tor hidden services (status: %s):</b><br>" % main.file_server.tor_manager.status
        for site_address, onion in list(main.file_server.tor_manager.site_onions.items()):
            yield "- %-34s: %s<br>" % (site_address, onion)

    def renderDbStats(self):
        yield "<br><br><b>Db</b>:<br>"
        for db in Db.opened_dbs:
            tables = [row["name"] for row in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()]
            table_rows = {}
            for table in tables:
                table_rows[table] = db.execute("SELECT COUNT(*) AS c FROM %s" % table).fetchone()["c"]
            db_size = os.path.getsize(db.db_path) / 1024.0 / 1024.0
            yield "- %.3fs: %s %.3fMB, table rows: %s<br>" % (
                time.time() - db.last_query_time, db.db_path, db_size, json.dumps(table_rows, sort_keys=True)
            )

    def renderSites(self):
        yield "<br><br><b>Sites</b>:"
        yield "<table>"
        yield "<tr><th>address</th> <th>connected</th> <th title='connected/good/total'>peers</th> <th>content.json</th> <th>out</th> <th>in</th>  </tr>"
        for site in list(self.server.sites.values()):
            yield self.formatTableRow([
                (
                    """<a href='#' onclick='document.getElementById("peers_%s").style.display="initial"; return false'>%s</a>""",
                    (site.address, site.address)
                ),
                ("%s", [peer.connection.id for peer in list(site.peers.values()) if peer.connection and peer.connection.connected]),
                ("%s/%s/%s", (
                    len([peer for peer in list(site.peers.values()) if peer.connection and peer.connection.connected]),
                    len(site.getConnectablePeers(100)),
                    len(site.peers)
                )),
                ("%s (loaded: %s)", (
                    len(site.content_manager.contents),
                    len([key for key, val in dict(site.content_manager.contents).items() if val])
                )),
                ("%.0fk", site.settings.get("bytes_sent", 0) / 1024),
                ("%.0fk", site.settings.get("bytes_recv", 0) / 1024),
            ], "serving-%s" % site.settings["serving"])
            yield "<tr><td id='peers_%s' style='display: none; white-space: pre' colspan=6>" % site.address
            for key, peer in list(site.peers.items()):
                if peer.time_found:
                    time_found = int(time.time() - peer.time_found) / 60
                else:
                    time_found = "--"
                if peer.connection:
                    connection_id = peer.connection.id
                else:
                    connection_id = None
                if site.content_manager.has_optional_files:
                    yield "Optional files: %4s " % len(peer.hashfield)
                time_added = (time.time() - peer.time_added) / (60 * 60 * 24)
                yield "(#%4s, rep: %2s, err: %s, found: %.1fs min, add: %.1f day) %30s -<br>" % (connection_id, peer.reputation, peer.connection_error, time_found, time_added, key)
            yield "<br></td></tr>"
        yield "</table>"

    def renderBigfiles(self):
        yield "<br><br><b>Big files</b>:<br>"
        for site in list(self.server.sites.values()):
            if not site.settings.get("has_bigfile"):
                continue
            bigfiles = {}
            yield """<a href="#" onclick='document.getElementById("bigfiles_%s").style.display="initial"; return false'>%s</a><br>""" % (site.address, site.address)
            for peer in list(site.peers.values()):
                if not peer.time_piecefields_updated:
                    continue
                for sha512, piecefield in peer.piecefields.items():
                    if sha512 not in bigfiles:
                        bigfiles[sha512] = []
                    bigfiles[sha512].append(peer)

            yield "<div id='bigfiles_%s' style='display: none'>" % site.address
            for sha512, peers in bigfiles.items():
                yield "<br> - " + sha512 + " (hash id: %s)<br>" % site.content_manager.hashfield.getHashId(sha512)
                yield "<table>"
                for peer in peers:
                    yield "<tr><td>" + peer.key + "</td><td>" + peer.piecefields[sha512].tostring() + "</td></tr>"
                yield "</table>"
            yield "</div>"

    def renderRequests(self):
        import main
        yield "<div style='float: left'>"
        yield "<br><br><b>Sent commands</b>:<br>"
        yield "<table>"
        for stat_key, stat in sorted(main.file_server.stat_sent.items(), key=lambda i: i[1]["bytes"], reverse=True):
            yield "<tr><td>%s</td><td style='white-space: nowrap'>x %s =</td><td>%.0fkB</td></tr>" % (stat_key, stat["num"], stat["bytes"] / 1024)
        yield "</table>"
        yield "</div>"

        yield "<div style='float: left; margin-left: 20%; max-width: 50%'>"
        yield "<br><br><b>Received commands</b>:<br>"
        yield "<table>"
        for stat_key, stat in sorted(main.file_server.stat_recv.items(), key=lambda i: i[1]["bytes"], reverse=True):
            yield "<tr><td>%s</td><td style='white-space: nowrap'>x %s =</td><td>%.0fkB</td></tr>" % (stat_key, stat["num"], stat["bytes"] / 1024)
        yield "</table>"
        yield "</div>"
        yield "<div style='clear: both'></div>"

    def renderMemory(self):
        import gc
        from Ui import UiRequest

        hpy = None
        if self.get.get("size") == "1":  # Calc obj size
            try:
                import guppy
                hpy = guppy.hpy()
            except Exception:
                pass
        self.sendHeader()

        # Object types

        obj_count = {}
        for obj in gc.get_objects():
            obj_type = str(type(obj))
            if obj_type not in obj_count:
                obj_count[obj_type] = [0, 0]
            obj_count[obj_type][0] += 1  # Count
            obj_count[obj_type][1] += float(sys.getsizeof(obj)) / 1024  # Size

        yield "<br><br><b>Objects in memory (types: %s, total: %s, %.2fkb):</b><br>" % (
            len(obj_count),
            sum([stat[0] for stat in list(obj_count.values())]),
            sum([stat[1] for stat in list(obj_count.values())])
        )

        for obj, stat in sorted(list(obj_count.items()), key=lambda x: x[1][0], reverse=True):  # Sorted by count
            yield " - %.1fkb = %s x <a href=\"/Listobj?type=%s\">%s</a><br>" % (stat[1], stat[0], obj, html.escape(obj))

        # Classes

        class_count = {}
        for obj in gc.get_objects():
            obj_type = str(type(obj))
            if obj_type != "<type 'instance'>":
                continue
            class_name = obj.__class__.__name__
            if class_name not in class_count:
                class_count[class_name] = [0, 0]
            class_count[class_name][0] += 1  # Count
            class_count[class_name][1] += float(sys.getsizeof(obj)) / 1024  # Size

        yield "<br><br><b>Classes in memory (types: %s, total: %s, %.2fkb):</b><br>" % (
            len(class_count),
            sum([stat[0] for stat in list(class_count.values())]),
            sum([stat[1] for stat in list(class_count.values())])
        )

        for obj, stat in sorted(list(class_count.items()), key=lambda x: x[1][0], reverse=True):  # Sorted by count
            yield " - %.1fkb = %s x <a href=\"/Dumpobj?class=%s\">%s</a><br>" % (stat[1], stat[0], obj, html.escape(obj))

        from greenlet import greenlet
        objs = [obj for obj in gc.get_objects() if isinstance(obj, greenlet)]
        yield "<br>Greenlets (%s):<br>" % len(objs)
        for obj in objs:
            yield " - %.1fkb: %s<br>" % (self.getObjSize(obj, hpy), html.escape(repr(obj)))

        from Worker import Worker
        objs = [obj for obj in gc.get_objects() if isinstance(obj, Worker)]
        yield "<br>Workers (%s):<br>" % len(objs)
        for obj in objs:
            yield " - %.1fkb: %s<br>" % (self.getObjSize(obj, hpy), html.escape(repr(obj)))

        from Connection import Connection
        objs = [obj for obj in gc.get_objects() if isinstance(obj, Connection)]
        yield "<br>Connections (%s):<br>" % len(objs)
        for obj in objs:
            yield " - %.1fkb: %s<br>" % (self.getObjSize(obj, hpy), html.escape(repr(obj)))

        from socket import socket
        objs = [obj for obj in gc.get_objects() if isinstance(obj, socket)]
        yield "<br>Sockets (%s):<br>" % len(objs)
        for obj in objs:
            yield " - %.1fkb: %s<br>" % (self.getObjSize(obj, hpy), html.escape(repr(obj)))

        from msgpack import Unpacker
        objs = [obj for obj in gc.get_objects() if isinstance(obj, Unpacker)]
        yield "<br>Msgpack unpacker (%s):<br>" % len(objs)
        for obj in objs:
            yield " - %.1fkb: %s<br>" % (self.getObjSize(obj, hpy), html.escape(repr(obj)))

        from Site.Site import Site
        objs = [obj for obj in gc.get_objects() if isinstance(obj, Site)]
        yield "<br>Sites (%s):<br>" % len(objs)
        for obj in objs:
            yield " - %.1fkb: %s<br>" % (self.getObjSize(obj, hpy), html.escape(repr(obj)))

        objs = [obj for obj in gc.get_objects() if isinstance(obj, self.server.log.__class__)]
        yield "<br>Loggers (%s):<br>" % len(objs)
        for obj in objs:
            yield " - %.1fkb: %s<br>" % (self.getObjSize(obj, hpy), html.escape(repr(obj.name)))

        objs = [obj for obj in gc.get_objects() if isinstance(obj, UiRequest)]
        yield "<br>UiRequests (%s):<br>" % len(objs)
        for obj in objs:
            yield " - %.1fkb: %s<br>" % (self.getObjSize(obj, hpy), html.escape(repr(obj)))

        from Peer import Peer
        objs = [obj for obj in gc.get_objects() if isinstance(obj, Peer)]
        yield "<br>Peers (%s):<br>" % len(objs)
        for obj in objs:
            yield " - %.1fkb: %s<br>" % (self.getObjSize(obj, hpy), html.escape(repr(obj)))

        objs = [(key, val) for key, val in sys.modules.items() if val is not None]
        objs.sort()
        yield "<br>Modules (%s):<br>" % len(objs)
        for module_name, module in objs:
            yield " - %.3fkb: %s %s<br>" % (self.getObjSize(module, hpy), module_name, html.escape(repr(module)))

    # /Stats entry point
    @helper.encodeResponse
    def actionStats(self):
        import gc

        self.sendHeader()

        if "Multiuser" in PluginManager.plugin_manager.plugin_names and not config.multiuser_local:
            yield "This function is disabled on this proxy"
            return

        s = time.time()

        # Style
        yield """
        <style>
         * { font-family: monospace }
         table td, table th { text-align: right; padding: 0px 10px }
         .connections td { white-space: nowrap }
         .serving-False { opacity: 0.3 }
        </style>
        """

        renderers = [
            self.renderHead(),
            self.renderConnectionsTable(),
            self.renderTrackers(),
            self.renderTor(),
            self.renderDbStats(),
            self.renderSites(),
            self.renderBigfiles(),
            self.renderRequests()

        ]

        for part in itertools.chain(*renderers):
            yield part

        if config.debug:
            for part in self.renderMemory():
                yield part

        gc.collect()  # Implicit grabage collection
        yield "Done in %.1f" % (time.time() - s)

    @helper.encodeResponse
    def actionDumpobj(self):

        import gc
        import sys

        self.sendHeader()

        if "Multiuser" in PluginManager.plugin_manager.plugin_names and not config.multiuser_local:
            yield "This function is disabled on this proxy"
            return

        # No more if not in debug mode
        if not config.debug:
            yield "Not in debug mode"
            return

        class_filter = self.get.get("class")

        yield """
        <style>
         * { font-family: monospace; white-space: pre }
         table * { text-align: right; padding: 0px 10px }
        </style>
        """

        objs = gc.get_objects()
        for obj in objs:
            obj_type = str(type(obj))
            if obj_type != "<type 'instance'>" or obj.__class__.__name__ != class_filter:
                continue
            yield "%.1fkb %s... " % (float(sys.getsizeof(obj)) / 1024, html.escape(str(obj)))
            for attr in dir(obj):
                yield "- %s: %s<br>" % (attr, html.escape(str(getattr(obj, attr))))
            yield "<br>"

        gc.collect()  # Implicit grabage collection

    @helper.encodeResponse
    def actionListobj(self):

        import gc
        import sys

        self.sendHeader()

        if "Multiuser" in PluginManager.plugin_manager.plugin_names and not config.multiuser_local:
            yield "This function is disabled on this proxy"
            return

        # No more if not in debug mode
        if not config.debug:
            yield "Not in debug mode"
            return

        type_filter = self.get.get("type")

        yield """
        <style>
         * { font-family: monospace; white-space: pre }
         table * { text-align: right; padding: 0px 10px }
        </style>
        """

        yield "Listing all %s objects in memory...<br>" % html.escape(type_filter)

        ref_count = {}
        objs = gc.get_objects()
        for obj in objs:
            obj_type = str(type(obj))
            if obj_type != type_filter:
                continue
            refs = [
                ref for ref in gc.get_referrers(obj)
                if hasattr(ref, "__class__") and
                ref.__class__.__name__ not in ["list", "dict", "function", "type", "frame", "WeakSet", "tuple"]
            ]
            if not refs:
                continue
            try:
                yield "%.1fkb <span title=\"%s\">%s</span>... " % (
                    float(sys.getsizeof(obj)) / 1024, html.escape(str(obj)), html.escape(str(obj)[0:100].ljust(100))
                )
            except Exception:
                continue
            for ref in refs:
                yield " ["
                if "object at" in str(ref) or len(str(ref)) > 100:
                    yield str(ref.__class__.__name__)
                else:
                    yield str(ref.__class__.__name__) + ":" + html.escape(str(ref))
                yield "] "
                ref_type = ref.__class__.__name__
                if ref_type not in ref_count:
                    ref_count[ref_type] = [0, 0]
                ref_count[ref_type][0] += 1  # Count
                ref_count[ref_type][1] += float(sys.getsizeof(obj)) / 1024  # Size
            yield "<br>"

        yield "<br>Object referrer (total: %s, %.2fkb):<br>" % (len(ref_count), sum([stat[1] for stat in list(ref_count.values())]))

        for obj, stat in sorted(list(ref_count.items()), key=lambda x: x[1][0], reverse=True)[0:30]:  # Sorted by count
            yield " - %.1fkb = %s x %s<br>" % (stat[1], stat[0], html.escape(str(obj)))

        gc.collect()  # Implicit grabage collection

    @helper.encodeResponse
    def actionGcCollect(self):
        import gc
        self.sendHeader()
        yield str(gc.collect())

    # /About entry point
    @helper.encodeResponse
    def actionEnv(self):
        import main

        self.sendHeader()

        yield """
        <style>
         * { font-family: monospace; white-space: pre; }
         h2 { font-size: 100%; margin-bottom: 0px; }
         small { opacity: 0.5; }
         table { border-collapse: collapse; }
         td { padding-right: 10px; }
        </style>
        """

        if "Multiuser" in PluginManager.plugin_manager.plugin_names and not config.multiuser_local:
            yield "This function is disabled on this proxy"
            return

        yield from main.actions.testEnv(format="html")


@PluginManager.registerTo("Actions")
class ActionsPlugin:
    def formatTable(self, *rows, format="text"):
        if format == "html":
            return self.formatTableHtml(*rows)
        else:
            return self.formatTableText(*rows)

    def formatHead(self, title, format="text"):
        if format == "html":
            return "<h2>%s</h2>" % title
        else:
            return "\n* %s\n" % title

    def formatTableHtml(self, *rows):
        yield "<table>"
        for row in rows:
            yield "<tr>"
            for col in row:
                yield "<td>%s</td>" % html.escape(str(col))
            yield "</tr>"
        yield "</table>"

    def formatTableText(self, *rows):
        for row in rows:
            yield " "
            for col in row:
                yield " " + str(col)
            yield "\n"

    def testEnv(self, format="text"):
        import gevent
        import msgpack
        import pkg_resources
        import importlib
        import coincurve
        import sqlite3
        from Crypt import CryptBitcoin

        yield "\n"

        yield from self.formatTable(
            ["ZeroNet version:", "%s rev%s" % (config.version, config.rev)],
            ["Python:", "%s" % sys.version],
            ["Platform:", "%s" % sys.platform],
            ["Crypt verify lib:", "%s" % CryptBitcoin.lib_verify_best],
            ["OpenSSL:", "%s" % CryptBitcoin.sslcrypto.ecc.get_backend()],
            ["Libsecp256k1:", "%s" % type(coincurve._libsecp256k1.lib).__name__],
            ["SQLite:", "%s, API: %s" % (sqlite3.sqlite_version, sqlite3.version)],
            format=format
        )


        yield self.formatHead("Libraries:")
        rows = []
        for lib_name in ["gevent", "greenlet", "msgpack", "base58", "rsa", "socks", "pyasn1", "gevent_ws", "websocket", "maxminddb"]:
            try:
                module = importlib.import_module(lib_name)
                if "__version__" in dir(module):
                    version = module.__version__
                elif "version" in dir(module):
                    version = module.version
                else:
                    version = "unknown version"

                if type(version) is tuple:
                    version = ".".join(map(str, version))

                rows.append(["- %s:" % lib_name, version, "at " + module.__file__])
            except Exception as err:
                rows.append(["! Error importing %s:", repr(err)])

            """
            try:
                yield " - %s<br>" % html.escape(repr(pkg_resources.get_distribution(lib_name)))
            except Exception as err:
                yield " ! %s<br>" % html.escape(repr(err))
            """

        yield from self.formatTable(*rows, format=format)

        yield self.formatHead("Library config:", format=format)

        yield from self.formatTable(
            ["- gevent:", gevent.config.loop.__module__],
            ["- msgpack unpacker:", msgpack.Unpacker.__module__],
            format=format
        )
