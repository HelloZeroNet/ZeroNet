#!/usr/bin/env python3

# Included modules
import os
import sys


def main():
    if sys.version_info.major < 3:
        print("Error: Python 3.x is required")
        sys.exit(1)

    # Test if Python is being ran in optimized mode (-O) because ZN relies on assert
    try:
        assert True is False # Intentionally get an AssertionError
    except AssertionError:
        pass
    else:
        print("Error: ZeroNet cannot be ran in optimized mode")
        sys.exit(1)
    
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

    args = sys.argv[:]

    sys.executable = sys.executable.replace(".pkg", "")  # Frozen mac fix

    if not getattr(sys, 'frozen', False):
        args.insert(0, sys.executable)

    # Don't open browser after restart
    if "--open_browser" in args:
        del args[args.index("--open_browser") + 1]  # argument value
        del args[args.index("--open_browser")]  # argument key

    if getattr(sys, 'frozen', False):
        pos_first_arg = 1  # Only the executable
    else:
        pos_first_arg = 2  # Interpter, .py file path

    args.insert(pos_first_arg, "--open_browser")
    args.insert(pos_first_arg + 1, "False")

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
