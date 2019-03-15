import os
import sys


def update():
    print("Updating not supported yet")
    return False

if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))  # Imports relative to src

    from gevent import monkey
    monkey.patch_all()

    from Config import config
    config.parse(silent=True)

    try:
        update()
    except Exception as err:
        print("Update error: %s" % err)
