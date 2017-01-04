#!/usr/bin/env python2.7

# Included modules
import os
import sys


def main():
    print "- Starting ZeroNet..."

    main = None
    try:
        app_dir = os.path.dirname(os.path.abspath(__file__))
        os.chdir(app_dir)  # Change working dir to zeronet.py dir
        sys.path.insert(0, os.path.join(app_dir, "src/lib"))  # External library directory
        sys.path.insert(0, os.path.join(app_dir, "src"))  # Imports relative to src
        import main
        main.start()
        if main.update_after_shutdown:  # Updater
            import gc
            import update
            # Try cleanup openssl
            try:
                if "lib.opensslVerify" in sys.modules:
                    sys.modules["lib.opensslVerify"].opensslVerify.closeLibrary()
            except Exception, err:
                print "Error closing opensslVerify lib", err
            try:
                if "lib.pyelliptic" in sys.modules:
                    sys.modules["lib.pyelliptic"].openssl.closeLibrary()
            except Exception, err:
                print "Error closing pyelliptic lib", err

            # Close lock file
            sys.modules["main"].lock.close()

            # Update
            update.update()

            # Close log files
            logger = sys.modules["main"].logging.getLogger()

            for handler in logger.handlers[:]:
                handler.flush()
                handler.close()
                logger.removeHandler(handler)


    except (Exception, ):  # Prevent closing
        import traceback
        traceback.print_exc()
        traceback.print_exc(file=open("log/error.log", "a"))

    if main and main.update_after_shutdown:  # Updater
        # Restart
        gc.collect()  # Garbage collect
        print "Restarting..."
        import time
        time.sleep(1)  # Wait files to close
        args = sys.argv[:]
        args.insert(0, sys.executable)
        if sys.platform == 'win32':
            args = ['"%s"' % arg for arg in args]
        os.execv(sys.executable, args)
        print "Bye."

if __name__ == '__main__':
    main()
