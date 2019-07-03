import re
import logging

from Plugin import PluginManager
from Config import config
from Debug import Debug
from util import SafeRe


class WsLogStreamer(logging.StreamHandler):
    def __init__(self, stream_id, ui_websocket, filter):
        self.stream_id = stream_id
        self.ui_websocket = ui_websocket

        if filter:
            if not SafeRe.isSafePattern(filter):
                raise Exception("Not a safe prex pattern")
            self.filter_re = re.compile(".*" + filter)
        else:
            self.filter_re = None
        return super(WsLogStreamer, self).__init__()

    def emit(self, record):
        if self.ui_websocket.ws.closed:
            self.stop()
            return
        line = self.format(record)
        if self.filter_re and not self.filter_re.match(line):
            return False

        self.ui_websocket.cmd("logLineAdd", {"stream_id": self.stream_id, "lines": [line]})

    def stop(self):
        logging.getLogger('').removeHandler(self)


@PluginManager.registerTo("UiWebsocket")
class UiWebsocketPlugin(object):
    def __init__(self, *args, **kwargs):
        self.admin_commands.update(["consoleLogRead", "consoleLogStream", "consoleLogStreamRemove"])
        self.log_streamers = {}
        return super(UiWebsocketPlugin, self).__init__(*args, **kwargs)

    def actionConsoleLogRead(self, to, filter=None, read_size=32 * 1024, limit=500):
        log_file_path = "%s/debug.log" % config.log_dir
        log_file = open(log_file_path, encoding="utf-8")
        log_file.seek(0, 2)
        end_pos = log_file.tell()
        log_file.seek(max(0, end_pos - read_size))
        if log_file.tell() != 0:
            log_file.readline()  # Partial line junk

        pos_start = log_file.tell()
        lines = []
        if filter:
            assert SafeRe.isSafePattern(filter)
            filter_re = re.compile(".*" + filter)

        for line in log_file:
            if filter and not filter_re.match(line):
                continue
            lines.append(line)

        num_found = len(lines)
        lines = lines[-limit:]

        return {"lines": lines, "pos_end": log_file.tell(), "pos_start": pos_start, "num_found": num_found}

    def addLogStreamer(self, stream_id, filter=None):
        logger = WsLogStreamer(stream_id, self, filter)
        logger.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)-8s %(name)s %(message)s'))
        logger.setLevel(logging.getLevelName("DEBUG"))

        logging.getLogger('').addHandler(logger)
        return logger

    def actionConsoleLogStream(self, to, filter=None):
        stream_id = to
        self.log_streamers[stream_id] = self.addLogStreamer(stream_id, filter)
        self.response(to, {"stream_id": stream_id})

    def actionConsoleLogStreamRemove(self, to, stream_id):
        try:
            self.log_streamers[stream_id].stop()
            del self.log_streamers[stream_id]
            return "ok"
        except Exception as err:
            return {"error": Debug.formatException(err)}
