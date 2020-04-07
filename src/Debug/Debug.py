import sys
import os
import re
from Config import config


# Non fatal exception
class Notify(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return self.message


def formatExceptionMessage(err):
    err_type = err.__class__.__name__
    if err.args:
        err_message = err.args[-1]
    else:
        err_message = err.__str__()
    return "%s: %s" % (err_type, err_message)


python_lib_dir = os.path.dirname(os.__file__)


def formatTraceback(items, limit=None, fold_builtin=True):
    back = []
    i = 0
    prev_file_title = ""
    is_prev_builtin = False

    for path, line in items:
        i += 1
        is_last = i == len(items)
        dir_name, file_name = os.path.split(path.replace("\\", "/"))

        plugin_match = re.match(".*/plugins/(.+)$", dir_name)
        if plugin_match:
            file_title = "%s/%s" % (plugin_match.group(1), file_name)
            is_prev_builtin = False
        elif path.startswith(python_lib_dir):
            if is_prev_builtin and not is_last and fold_builtin:
                if back[-1] != "...":
                    back.append("...")
                continue
            else:
                file_title = path.replace(python_lib_dir, "").replace("\\", "/").strip("/").replace("site-packages/", "")
            is_prev_builtin = True
        else:
            file_title = file_name
            is_prev_builtin = False

        if file_title == prev_file_title:
            back.append("%s" % line)
        else:
            back.append("%s line %s" % (file_title, line))

        prev_file_title = file_title

        if limit and i >= limit:
            back.append("...")
            break
    return back


def formatException(err=None, format="text"):
    import traceback
    if type(err) == Notify:
        return err
    elif type(err) == tuple and err and err[0] is not None:  # Passed trackeback info
        exc_type, exc_obj, exc_tb = err
        err = None
    else:  # No trackeback info passed, get latest
        exc_type, exc_obj, exc_tb = sys.exc_info()

    if not err:
        if hasattr(err, "message"):
            err = exc_obj.message
        else:
            err = exc_obj

    tb = formatTraceback([[frame[0], frame[1]] for frame in traceback.extract_tb(exc_tb)])
    if format == "html":
        return "%s: %s<br><small class='multiline'>%s</small>" % (repr(err), err, " > ".join(tb))
    else:
        return "%s: %s in %s" % (exc_type.__name__, err, " > ".join(tb))


def formatStack(limit=None):
    import inspect
    tb = formatTraceback([[frame[1], frame[2]] for frame in inspect.stack()[1:]], limit=limit)
    return " > ".join(tb)


# Test if gevent eventloop blocks
import logging
import gevent
import time


num_block = 0
def testBlock():
    global num_block
    logging.debug("Gevent block checker started")
    last_time = time.time()
    while 1:
        time.sleep(1)
        if time.time() - last_time > 1.1:
            logging.debug("Gevent block detected: %.3fs" % (time.time() - last_time - 1))
            num_block += 1
        last_time = time.time()
gevent.spawn(testBlock)


if __name__ == "__main__":
    try:
        print(1 / 0)
    except Exception as err:
        print(type(err).__name__)
        print("1/0 error: %s" % formatException(err))

    def loadJson():
        json.loads("Errr")

    import json
    try:
        loadJson()
    except Exception as err:
        print(err)
        print("Json load error: %s" % formatException(err))

    try:
        raise Notify("nothing...")
    except Exception as err:
        print("Notify: %s" % formatException(err))

    loadJson()
