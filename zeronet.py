#!/usr/bin/env python3

# Included modules
import os
import sys


def main():
    if sys.version_info.major < 3:
        print("Error: Python 3.x is required")
        sys.exit(0)

    if "--silent" not in sys.argv:
        print("- Starting ZeroNet...")

    main = None
    try:
        import main
        main.start()
    except Exception as err:  # Prevent closing
        import traceback
        try:
            import logging
            logging.exception("Unhandled exception: %s" % err)
        except Exception as log_err:
            print("Failed to log error:", log_err)
            traceback.print_exc()
        from Config import config
        traceback.print_exc(file=open(config.log_dir + "/error.log", "a"))

    if main and (main.update_after_shutdown or main.restart_after_shutdown):  # Updater
        if main.update_after_shutdown:
            import update
            if sys.platform.startswith("win"):
                update.update(restart_win=True)
            else:
                update.update()
                restart()
        else:
            print("Restarting...")
            restart()


def restart():
    if "main" in sys.modules:
        import atexit
        # Close log files
        logger = sys.modules["main"].logging.getLogger()

        for handler in logger.handlers[:]:
            handler.flush()
            handler.close()
            logger.removeHandler(handler)

        atexit._run_exitfuncs()
        import time
        time.sleep(1)  # Wait files to close

    args = [arg for arg in sys.argv[:] if arg not in ("--open_browser", "default_browser")]

    sys.executable = sys.executable.replace(".pkg", "")  # Frozen mac fix

    if not getattr(sys, 'frozen', False):
        args.insert(0, sys.executable)

    if sys.platform == 'win32':
        args = ['"%s"' % arg for arg in args]

    try:
        print("Executing %s %s" % (sys.executable, args))
        os.execv(sys.executable, args)
    except Exception as err:
        print("Execv error: %s" % err)
    print("Bye.")


def start():
    app_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(app_dir)  # Change working dir to zeronet.py dir
    sys.path.insert(0, os.path.join(app_dir, "src/lib"))  # External liblary directory
    sys.path.insert(0, os.path.join(app_dir, "src"))  # Imports relative to src

    if "--update" in sys.argv:
        sys.argv.remove("--update")
        print("Updating...")
        import update
        update.update()
    else:
        main()


if __name__ == '__main__':
    start()
