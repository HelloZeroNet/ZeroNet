import time
import cgi
import os

from Plugin import PluginManager
from Config import config


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

    # /Stats entry point
    def actionStats(self):
        import gc
        import sys
        from Ui import UiRequest
        from Db import Db
        from Crypt import CryptConnection

        hpy = None
        if self.get.get("size") == "1":  # Calc obj size
            try:
                import guppy
                hpy = guppy.hpy()
            except:
                pass
        self.sendHeader()

        if "Multiuser" in PluginManager.plugin_manager.plugin_names and not config.multiuser_local:
            yield "This function is disabled on this proxy"
            raise StopIteration

        s = time.time()
        main = sys.modules["main"]

        # Style
        yield """
        <style>
         * { font-family: monospace }
         table td, table th { text-align: right; padding: 0px 10px }
         .connections td { white-space: nowrap }
         .serving-False { opacity: 0.3 }
        </style>
        """

        # Memory
        try:
            yield "rev%s | " % config.rev
            yield "%s | " % config.ip_external
            yield "Opened: %s | " % main.file_server.port_opened
            yield "Crypt: %s | " % CryptConnection.manager.crypt_supported
            yield "In: %.2fMB, Out: %.2fMB  | " % (
                float(main.file_server.bytes_recv) / 1024 / 1024,
                float(main.file_server.bytes_sent) / 1024 / 1024
            )
            yield "Peerid: %s  | " % main.file_server.peer_id
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

        # Connections
        yield "<b>Connections</b> (%s, total made: %s):<br>" % (
            len(main.file_server.connections), main.file_server.last_connection_id
        )
        yield "<table class='connections'><tr> <th>id</th> <th>type</th> <th>ip</th> <th>open</th> <th>crypt</th> <th>ping</th>"
        yield "<th>buff</th> <th>bad</th> <th>idle</th> <th>open</th> <th>delay</th> <th>cpu</th> <th>out</th> <th>in</th> <th>last sent</th>"
        yield "<th>wait</th> <th>version</th> <th>sites</th> </tr>"
        for connection in main.file_server.connections:
            if "cipher" in dir(connection.sock):
                cipher = connection.sock.cipher()[0]
            else:
                cipher = connection.crypt
            yield self.formatTableRow([
                ("%3d", connection.id),
                ("%s", connection.type),
                ("%s:%s", (connection.ip, connection.port)),
                ("%s", connection.handshake.get("port_opened")),
                ("<span title='%s'>%s</span>", (connection.crypt, cipher)),
                ("%6.3f", connection.last_ping_delay),
                ("%s", connection.incomplete_buff_recv),
                ("%s", connection.bad_actions),
                ("since", max(connection.last_send_time, connection.last_recv_time)),
                ("since", connection.start_time),
                ("%.3f", connection.last_sent_time - connection.last_send_time),
                ("%.3f", connection.cpu_time),
                ("%.0fkB", connection.bytes_sent / 1024),
                ("%.0fkB", connection.bytes_recv / 1024),
                ("%s", connection.last_cmd),
                ("%s", connection.waiting_requests.keys()),
                ("%s r%s", (connection.handshake.get("version"), connection.handshake.get("rev", "?"))),
                ("%s", connection.sites)
            ])
        yield "</table>"

        # Tor hidden services
        yield "<br><br><b>Tor hidden services (status: %s):</b><br>" % main.file_server.tor_manager.status
        for site_address, onion in main.file_server.tor_manager.site_onions.items():
            yield "- %-34s: %s<br>" % (site_address, onion)

        # Db
        yield "<br><br><b>Db</b>:<br>"
        for db in sys.modules["Db.Db"].opened_dbs:
            yield "- %.3fs: %s<br>" % (time.time() - db.last_query_time, db.db_path.encode("utf8"))

        # Sites
        yield "<br><br><b>Sites</b>:"
        yield "<table>"
        yield "<tr><th>address</th> <th>connected</th> <th title='connected/good/total'>peers</th> <th>content.json</th> <th>out</th> <th>in</th>  </tr>"
        for site in sorted(self.server.sites.values(), lambda a, b: cmp(a.address,b.address)):
            yield self.formatTableRow([
                (
                    """<a href='#' onclick='document.getElementById("peers_%s").style.display="initial"; return false'>%s</a>""",
                    (site.address, site.address)
                ),
                ("%s", [peer.connection.id for peer in site.peers.values() if peer.connection and peer.connection.connected]),
                ("%s/%s/%s", (
                    len([peer for peer in site.peers.values() if peer.connection and peer.connection.connected]),
                    len(site.getConnectablePeers(100)),
                    len(site.peers)
                )),
                ("%s (loaded: %s)", (
                    len(site.content_manager.contents),
                    len([key for key, val in dict(site.content_manager.contents).iteritems() if val])
                )),
                ("%.0fkB", site.settings.get("bytes_sent", 0) / 1024),
                ("%.0fkB", site.settings.get("bytes_recv", 0) / 1024),
            ], "serving-%s" % site.settings["serving"])
            yield "<tr><td id='peers_%s' style='display: none; white-space: pre' colspan=6>" % site.address
            for key, peer in site.peers.items():
                if peer.time_found:
                    time_found = int(time.time() - peer.time_found) / 60
                else:
                    time_found = "--"
                if peer.connection:
                    connection_id = peer.connection.id
                else:
                    connection_id = None
                if site.content_manager.hashfield:
                    yield "Optional files: %4s " % len(peer.hashfield)
                time_added = (time.time() - peer.time_added) / (60 * 60 * 24)
                yield "(#%4s, err: %s, found: %3s min, add: %.1f day) %30s -<br>" % (connection_id, peer.connection_error, time_found, time_added, key)
            yield "<br></td></tr>"
        yield "</table>"

        # No more if not in debug mode
        if not config.debug:
            raise StopIteration

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
            sum([stat[0] for stat in obj_count.values()]),
            sum([stat[1] for stat in obj_count.values()])
        )

        for obj, stat in sorted(obj_count.items(), key=lambda x: x[1][0], reverse=True):  # Sorted by count
            yield " - %.1fkb = %s x <a href=\"/Listobj?type=%s\">%s</a><br>" % (stat[1], stat[0], obj, cgi.escape(obj))

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
            sum([stat[0] for stat in class_count.values()]),
            sum([stat[1] for stat in class_count.values()])
        )

        for obj, stat in sorted(class_count.items(), key=lambda x: x[1][0], reverse=True):  # Sorted by count
            yield " - %.1fkb = %s x <a href=\"/Dumpobj?class=%s\">%s</a><br>" % (stat[1], stat[0], obj, cgi.escape(obj))

        from greenlet import greenlet
        objs = [obj for obj in gc.get_objects() if isinstance(obj, greenlet)]
        yield "<br>Greenlets (%s):<br>" % len(objs)
        for obj in objs:
            yield " - %.1fkb: %s<br>" % (self.getObjSize(obj, hpy), cgi.escape(repr(obj).encode("utf8")))

        from Worker import Worker
        objs = [obj for obj in gc.get_objects() if isinstance(obj, Worker)]
        yield "<br>Workers (%s):<br>" % len(objs)
        for obj in objs:
            yield " - %.1fkb: %s<br>" % (self.getObjSize(obj, hpy), cgi.escape(repr(obj)))

        from Connection import Connection
        objs = [obj for obj in gc.get_objects() if isinstance(obj, Connection)]
        yield "<br>Connections (%s):<br>" % len(objs)
        for obj in objs:
            yield " - %.1fkb: %s<br>" % (self.getObjSize(obj, hpy), cgi.escape(repr(obj)))

        from socket import socket
        objs = [obj for obj in gc.get_objects() if isinstance(obj, socket)]
        yield "<br>Sockets (%s):<br>" % len(objs)
        for obj in objs:
            yield " - %.1fkb: %s<br>" % (self.getObjSize(obj, hpy), cgi.escape(repr(obj)))

        from msgpack import Unpacker
        objs = [obj for obj in gc.get_objects() if isinstance(obj, Unpacker)]
        yield "<br>Msgpack unpacker (%s):<br>" % len(objs)
        for obj in objs:
            yield " - %.1fkb: %s<br>" % (self.getObjSize(obj, hpy), cgi.escape(repr(obj)))

        from Site import Site
        objs = [obj for obj in gc.get_objects() if isinstance(obj, Site)]
        yield "<br>Sites (%s):<br>" % len(objs)
        for obj in objs:
            yield " - %.1fkb: %s<br>" % (self.getObjSize(obj, hpy), cgi.escape(repr(obj)))

        objs = [obj for obj in gc.get_objects() if isinstance(obj, self.server.log.__class__)]
        yield "<br>Loggers (%s):<br>" % len(objs)
        for obj in objs:
            yield " - %.1fkb: %s<br>" % (self.getObjSize(obj, hpy), cgi.escape(repr(obj.name)))

        objs = [obj for obj in gc.get_objects() if isinstance(obj, UiRequest)]
        yield "<br>UiRequests (%s):<br>" % len(objs)
        for obj in objs:
            yield " - %.1fkb: %s<br>" % (self.getObjSize(obj, hpy), cgi.escape(repr(obj)))

        from Peer import Peer
        objs = [obj for obj in gc.get_objects() if isinstance(obj, Peer)]
        yield "<br>Peers (%s):<br>" % len(objs)
        for obj in objs:
            yield " - %.1fkb: %s<br>" % (self.getObjSize(obj, hpy), cgi.escape(repr(obj)))

        objs = [(key, val) for key, val in sys.modules.iteritems() if val is not None]
        objs.sort()
        yield "<br>Modules (%s):<br>" % len(objs)
        for module_name, module in objs:
            yield " - %.3fkb: %s %s<br>" % (self.getObjSize(module, hpy), module_name, cgi.escape(repr(module)))

        gc.collect()  # Implicit grabage collection
        yield "Done in %.1f" % (time.time() - s)

    def actionDumpobj(self):

        import gc
        import sys

        self.sendHeader()

        if "Multiuser" in PluginManager.plugin_manager.plugin_names and not config.multiuser_local:
            yield "This function is disabled on this proxy"
            raise StopIteration

        # No more if not in debug mode
        if not config.debug:
            yield "Not in debug mode"
            raise StopIteration

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
            yield "%.1fkb %s... " % (float(sys.getsizeof(obj)) / 1024, cgi.escape(str(obj)))
            for attr in dir(obj):
                yield "- %s: %s<br>" % (attr, cgi.escape(str(getattr(obj, attr))))
            yield "<br>"

        gc.collect()  # Implicit grabage collection

    def actionListobj(self):

        import gc
        import sys

        self.sendHeader()

        if "Multiuser" in PluginManager.plugin_manager.plugin_names and not config.multiuser_local:
            yield "This function is disabled on this proxy"
            raise StopIteration

        # No more if not in debug mode
        if not config.debug:
            yield "Not in debug mode"
            raise StopIteration

        type_filter = self.get.get("type")

        yield """
        <style>
         * { font-family: monospace; white-space: pre }
         table * { text-align: right; padding: 0px 10px }
        </style>
        """

        yield "Listing all %s objects in memory...<br>" % cgi.escape(type_filter)

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
                    float(sys.getsizeof(obj)) / 1024, cgi.escape(str(obj)), cgi.escape(str(obj)[0:100].ljust(100))
                )
            except:
                continue
            for ref in refs:
                yield " ["
                if "object at" in str(ref) or len(str(ref)) > 100:
                    yield str(ref.__class__.__name__)
                else:
                    yield str(ref.__class__.__name__) + ":" + cgi.escape(str(ref))
                yield "] "
                ref_type = ref.__class__.__name__
                if ref_type not in ref_count:
                    ref_count[ref_type] = [0, 0]
                ref_count[ref_type][0] += 1  # Count
                ref_count[ref_type][1] += float(sys.getsizeof(obj)) / 1024  # Size
            yield "<br>"

        yield "<br>Object referrer (total: %s, %.2fkb):<br>" % (len(ref_count), sum([stat[1] for stat in ref_count.values()]))

        for obj, stat in sorted(ref_count.items(), key=lambda x: x[1][0], reverse=True)[0:30]:  # Sorted by count
            yield " - %.1fkb = %s x %s<br>" % (stat[1], stat[0], cgi.escape(str(obj)))

        gc.collect()  # Implicit grabage collection

    def actionBenchmark(self):
        import sys
        import gc
        from contextlib import contextmanager

        output = self.sendHeader()

        if "Multiuser" in PluginManager.plugin_manager.plugin_names and not config.multiuser_local:
            yield "This function is disabled on this proxy"
            raise StopIteration

        @contextmanager
        def benchmark(name, standard):
            s = time.time()
            output("- %s" % name)
            try:
                yield 1
            except Exception, err:
                output("<br><b>! Error: %s</b><br>" % err)
            taken = time.time() - s
            if taken > 0:
                multipler = standard / taken
            else:
                multipler = 99
            if multipler < 0.3:
                speed = "Sloooow"
            elif multipler < 0.5:
                speed = "Ehh"
            elif multipler < 0.8:
                speed = "Goodish"
            elif multipler < 1.2:
                speed = "OK"
            elif multipler < 1.7:
                speed = "Fine"
            elif multipler < 2.5:
                speed = "Fast"
            elif multipler < 3.5:
                speed = "WOW"
            else:
                speed = "Insane!!"
            output("%.3fs [x%.2f: %s]<br>" % (taken, multipler, speed))
            time.sleep(0.01)

        yield """
        <style>
         * { font-family: monospace }
         table * { text-align: right; padding: 0px 10px }
        </style>
        """

        yield "Benchmarking ZeroNet %s (rev%s) Python %s on: %s...<br>" % (config.version, config.rev, sys.version, sys.platform)

        t = time.time()

        # CryptBitcoin
        yield "<br>CryptBitcoin:<br>"
        from Crypt import CryptBitcoin

        # seed = CryptBitcoin.newSeed()
        # yield "- Seed: %s<br>" % seed
        seed = "e180efa477c63b0f2757eac7b1cce781877177fe0966be62754ffd4c8592ce38"

        with benchmark("hdPrivatekey x 10", 0.7):
            for i in range(10):
                privatekey = CryptBitcoin.hdPrivatekey(seed, i * 10)
                yield "."
            valid = "5JsunC55XGVqFQj5kPGK4MWgTL26jKbnPhjnmchSNPo75XXCwtk"
            assert privatekey == valid, "%s != %s" % (privatekey, valid)

        data = "Hello" * 1024  # 5k
        with benchmark("sign x 10", 0.35):
            for i in range(10):
                yield "."
                sign = CryptBitcoin.sign(data, privatekey)
            valid = "HFGXaDauZ8vX/N9Jn+MRiGm9h+I94zUhDnNYFaqMGuOi+4+BbWHjuwmx0EaKNV1G+kP0tQDxWu0YApxwxZbSmZU="
            assert sign == valid, "%s != %s" % (sign, valid)

        address = CryptBitcoin.privatekeyToAddress(privatekey)
        if CryptBitcoin.opensslVerify:  # Openssl avalible
            with benchmark("openssl verify x 100", 0.37):
                for i in range(100):
                    if i % 10 == 0:
                        yield "."
                    ok = CryptBitcoin.verify(data, address, sign)
                assert ok, "does not verify from %s" % address
        else:
            yield " - openssl verify x 100...not avalible :(<br>"

        openssl_verify_bk = CryptBitcoin.opensslVerify  # Emulate openssl not found in any way
        CryptBitcoin.opensslVerify = None
        with benchmark("pure-python verify x 10", 1.6):
            for i in range(10):
                yield "."
                ok = CryptBitcoin.verify(data, address, sign)
            assert ok, "does not verify from %s" % address
        CryptBitcoin.opensslVerify = openssl_verify_bk

        # CryptHash
        yield "<br>CryptHash:<br>"
        from Crypt import CryptHash
        from cStringIO import StringIO

        data = StringIO("Hello" * 1024 * 1024)  # 5m
        with benchmark("sha256 5M x 10", 0.6):
            for i in range(10):
                data.seek(0)
                hash = CryptHash.sha256sum(data)
                yield "."
            valid = "8cd629d9d6aff6590da8b80782a5046d2673d5917b99d5603c3dcb4005c45ffa"
            assert hash == valid, "%s != %s" % (hash, valid)

        data = StringIO("Hello" * 1024 * 1024)  # 5m
        with benchmark("sha512 5M x 10", 0.6):
            for i in range(10):
                data.seek(0)
                hash = CryptHash.sha512sum(data)
                yield "."
            valid = "9ca7e855d430964d5b55b114e95c6bbb114a6d478f6485df93044d87b108904d"
            assert hash == valid, "%s != %s" % (hash, valid)

        with benchmark("os.urandom(256) x 1000", 0.0065):
            for i in range(10):
                for y in range(100):
                    data = os.urandom(256)
                yield "."

        # Msgpack
        import msgpack
        yield "<br>Msgpack: (version: %s)<br>" % ".".join(map(str, msgpack.version))
        binary = 'fqv\xf0\x1a"e\x10,\xbe\x9cT\x9e(\xa5]u\x072C\x8c\x15\xa2\xa8\x93Sw)\x19\x02\xdd\t\xfb\xf67\x88\xd9\xee\x86\xa1\xe4\xb6,\xc6\x14\xbb\xd7$z\x1d\xb2\xda\x85\xf5\xa0\x97^\x01*\xaf\xd3\xb0!\xb7\x9d\xea\x89\xbbh8\xa1"\xa7]e(@\xa2\xa5g\xb7[\xae\x8eE\xc2\x9fL\xb6s\x19\x19\r\xc8\x04S\xd0N\xe4]?/\x01\xea\xf6\xec\xd1\xb3\xc2\x91\x86\xd7\xf4K\xdf\xc2lV\xf4\xe8\x80\xfc\x8ep\xbb\x82\xb3\x86\x98F\x1c\xecS\xc8\x15\xcf\xdc\xf1\xed\xfc\xd8\x18r\xf9\x80\x0f\xfa\x8cO\x97(\x0b]\xf1\xdd\r\xe7\xbf\xed\x06\xbd\x1b?\xc5\xa0\xd7a\x82\xf3\xa8\xe6@\xf3\ri\xa1\xb10\xf6\xd4W\xbc\x86\x1a\xbb\xfd\x94!bS\xdb\xaeM\x92\x00#\x0b\xf7\xad\xe9\xc2\x8e\x86\xbfi![%\xd31]\xc6\xfc2\xc9\xda\xc6v\x82P\xcc\xa9\xea\xb9\xff\xf6\xc8\x17iD\xcf\xf3\xeeI\x04\xe9\xa1\x19\xbb\x01\x92\xf5nn4K\xf8\xbb\xc6\x17e>\xa7 \xbbv'
        data = {"int": 1024*1024*1024, "float": 12345.67890, "text": "hello"*1024, "binary": binary}
        with benchmark("pack 5K x 10 000", 0.78):
            for i in range(10):
                for y in range(1000):
                    data_packed = msgpack.packb(data)
                yield "."
            valid = """\x84\xa3int\xce@\x00\x00\x00\xa4text\xda\x14\x00hellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohellohello\xa5float\xcb@\xc8\x1c\xd6\xe61\xf8\xa1\xa6binary\xda\x01\x00fqv\xf0\x1a"e\x10,\xbe\x9cT\x9e(\xa5]u\x072C\x8c\x15\xa2\xa8\x93Sw)\x19\x02\xdd\t\xfb\xf67\x88\xd9\xee\x86\xa1\xe4\xb6,\xc6\x14\xbb\xd7$z\x1d\xb2\xda\x85\xf5\xa0\x97^\x01*\xaf\xd3\xb0!\xb7\x9d\xea\x89\xbbh8\xa1"\xa7]e(@\xa2\xa5g\xb7[\xae\x8eE\xc2\x9fL\xb6s\x19\x19\r\xc8\x04S\xd0N\xe4]?/\x01\xea\xf6\xec\xd1\xb3\xc2\x91\x86\xd7\xf4K\xdf\xc2lV\xf4\xe8\x80\xfc\x8ep\xbb\x82\xb3\x86\x98F\x1c\xecS\xc8\x15\xcf\xdc\xf1\xed\xfc\xd8\x18r\xf9\x80\x0f\xfa\x8cO\x97(\x0b]\xf1\xdd\r\xe7\xbf\xed\x06\xbd\x1b?\xc5\xa0\xd7a\x82\xf3\xa8\xe6@\xf3\ri\xa1\xb10\xf6\xd4W\xbc\x86\x1a\xbb\xfd\x94!bS\xdb\xaeM\x92\x00#\x0b\xf7\xad\xe9\xc2\x8e\x86\xbfi![%\xd31]\xc6\xfc2\xc9\xda\xc6v\x82P\xcc\xa9\xea\xb9\xff\xf6\xc8\x17iD\xcf\xf3\xeeI\x04\xe9\xa1\x19\xbb\x01\x92\xf5nn4K\xf8\xbb\xc6\x17e>\xa7 \xbbv"""
            assert data_packed == valid, "%s<br>!=<br>%s" % (repr(data_packed), repr(valid))

        with benchmark("unpack 5K x 10 000", 1.2):
            for i in range(10):
                for y in range(1000):
                    data_unpacked = msgpack.unpackb(data_packed)
                yield "."
            assert data == data_unpacked, "%s != %s" % (data_unpack, data)

        with benchmark("streaming unpack 5K x 10 000", 1.4):
            for i in range(10):
                unpacker = msgpack.Unpacker()
                for y in range(1000):
                    unpacker.feed(data_packed)
                    for data_unpacked in unpacker:
                        pass
                yield "."
            assert data == data_unpacked, "%s != %s" % (data_unpack, data)

        # Db
        from Db import Db
        import sqlite3
        yield "<br>Db: (version: %s, API: %s)<br>" % (sqlite3.sqlite_version, sqlite3.version)

        schema = {
            "db_name": "TestDb",
            "db_file": "%s/benchmark.db" % config.data_dir,
            "maps": {
                ".*": {
                    "to_table": {
                        "test": "test"
                    }
                }
            },
            "tables": {
                "test": {
                    "cols": [
                        ["test_id", "INTEGER"],
                        ["title", "TEXT"],
                        ["json_id", "INTEGER REFERENCES json (json_id)"]
                    ],
                    "indexes": ["CREATE UNIQUE INDEX test_key ON test(test_id, json_id)"],
                    "schema_changed": 1426195822
                }
            }
        }

        if os.path.isfile("%s/benchmark.db" % config.data_dir):
            os.unlink("%s/benchmark.db" % config.data_dir)

        with benchmark("Open x 10", 0.13):
            for i in range(10):
                db = Db(schema, "%s/benchmark.db" % config.data_dir)
                db.checkTables()
                db.close()
                yield "."

        db = Db(schema, "%s/benchmark.db" % config.data_dir)
        db.checkTables()
        import json

        with benchmark("Insert x 10 x 1000", 1.0):
            for u in range(10):  # 10 user
                data = {"test": []}
                for i in range(1000):  # 1000 line of data
                    data["test"].append({"test_id": i, "title": "Testdata for %s message %s" % (u, i)})
                json.dump(data, open("%s/test_%s.json" % (config.data_dir, u), "w"))
                db.updateJson("%s/test_%s.json" % (config.data_dir, u))
                os.unlink("%s/test_%s.json" % (config.data_dir, u))
                yield "."

        with benchmark("Buffered insert x 100 x 100", 1.3):
            cur = db.getCursor()
            cur.execute("BEGIN")
            cur.logging = False
            for u in range(100, 200):  # 100 user
                data = {"test": []}
                for i in range(100):  # 1000 line of data
                    data["test"].append({"test_id": i, "title": "Testdata for %s message %s" % (u, i)})
                json.dump(data, open("%s/test_%s.json" % (config.data_dir, u), "w"))
                db.updateJson("%s/test_%s.json" % (config.data_dir, u), cur=cur)
                os.unlink("%s/test_%s.json" % (config.data_dir, u))
                if u % 10 == 0:
                    yield "."
            cur.execute("COMMIT")

        yield " - Total rows in db: %s<br>" % db.execute("SELECT COUNT(*) AS num FROM test").fetchone()[0]

        with benchmark("Indexed query x 1000", 0.25):
            found = 0
            cur = db.getCursor()
            cur.logging = False
            for i in range(1000):  # 1000x by test_id
                res = cur.execute("SELECT * FROM test WHERE test_id = %s" % i)
                for row in res:
                    found += 1
                if i % 100 == 0:
                    yield "."

            assert found == 20000, "Found: %s != 20000" % found

        with benchmark("Not indexed query x 100", 0.6):
            found = 0
            cur = db.getCursor()
            cur.logging = False
            for i in range(100):  # 1000x by test_id
                res = cur.execute("SELECT * FROM test WHERE json_id = %s" % i)
                for row in res:
                    found += 1
                if i % 10 == 0:
                    yield "."

            assert found == 18900, "Found: %s != 18900" % found

        with benchmark("Like query x 100", 1.8):
            found = 0
            cur = db.getCursor()
            cur.logging = False
            for i in range(100):  # 1000x by test_id
                res = cur.execute("SELECT * FROM test WHERE title LIKE '%%message %s%%'" % i)
                for row in res:
                    found += 1
                if i % 10 == 0:
                    yield "."

            assert found == 38900, "Found: %s != 11000" % found

        db.close()
        if os.path.isfile("%s/benchmark.db" % config.data_dir):
            os.unlink("%s/benchmark.db" % config.data_dir)

        gc.collect()  # Implicit grabage collection

        yield "<br>Done. Total: %.2fs" % (time.time() - t)

    def actionGcCollect(self):
        import gc
        self.sendHeader()
        yield str(gc.collect())
