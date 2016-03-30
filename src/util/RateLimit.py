import time
import gevent
import logging

log = logging.getLogger("RateLimit")

called_db = {}  # Holds events last call time
queue_db = {}  # Commands queued to run

# Register event as called
# Return: None


def called(event, penalty=0):
    called_db[event] = time.time() + penalty


# Check if calling event is allowed
# Return: True if allowed False if not
def isAllowed(event, allowed_again=10):
    last_called = called_db.get(event)
    if not last_called:  # Its not called before
        return True
    elif time.time() - last_called >= allowed_again:
        del called_db[event]  # Delete last call time to save memory
        return True
    else:
        return False

def delayLeft(event, allowed_again=10):
    last_called = called_db.get(event)
    if not last_called:  # Its not called before
        return 0
    else:
        return allowed_again - (time.time() - last_called)

def callQueue(event):
    func, args, kwargs, thread = queue_db[event]
    log.debug("Calling: %s" % event)
    del called_db[event]
    del queue_db[event]
    return func(*args, **kwargs)


# Rate limit and delay function call if necessary
# If the function called again within the rate limit interval then previous queued call will be dropped
# Return: Immediately gevent thread
def callAsync(event, allowed_again=10, func=None, *args, **kwargs):
    if isAllowed(event, allowed_again):  # Not called recently, call it now
        called(event)
        # print "Calling now"
        return gevent.spawn(func, *args, **kwargs)
    else:  # Called recently, schedule it for later
        time_left = allowed_again - max(0, time.time() - called_db[event])
        log.debug("Added to queue (%.2fs left): %s " % (time_left, event))
        if not queue_db.get(event):  # Function call not queued yet
            thread = gevent.spawn_later(time_left, lambda: callQueue(event))  # Call this function later
            queue_db[event] = (func, args, kwargs, thread)
            return thread
        else:  # Function call already queued, just update the parameters
            thread = queue_db[event][3]
            queue_db[event] = (func, args, kwargs, thread)
            return thread


# Rate limit and delay function call if needed
# Return: Wait for execution/delay then return value
def call(event, allowed_again=10, func=None, *args, **kwargs):
    if isAllowed(event):  # Not called recently, call it now
        called(event)
        # print "Calling now", allowed_again
        return func(*args, **kwargs)

    else:  # Called recently, schedule it for later
        time_left = max(0, allowed_again - (time.time() - called_db[event]))
        # print "Time left: %s" % time_left, args, kwargs
        log.debug("Calling sync (%.2fs left): %s" % (time_left, event))
        called(event, time_left)
        time.sleep(time_left)
        back = func(*args, **kwargs)
        if event in called_db:
            del called_db[event]
        return back


# Cleanup expired events every 3 minutes
def rateLimitCleanup():
    while 1:
        expired = time.time() - 60 * 2  # Cleanup if older than 2 minutes
        for event in called_db.keys():
            if called_db[event] < expired:
                del called_db[event]
        time.sleep(60 * 3)  # Every 3 minutes
gevent.spawn(rateLimitCleanup)


if __name__ == "__main__":
    from gevent import monkey
    monkey.patch_all()
    import random

    def publish(inner_path):
        print "Publishing %s..." % inner_path
        return 1

    def cb(thread):
        print "Value:", thread.value

    print "Testing async spam requests rate limit to 1/sec..."
    for i in range(3000):
        thread = callAsync("publish content.json", 1, publish, "content.json %s" % i)
        time.sleep(float(random.randint(1, 20)) / 100000)
    print thread.link(cb)
    print "Done"

    time.sleep(2)

    print "Testing sync spam requests rate limit to 1/sec..."
    for i in range(5):
        call("publish data.json", 1, publish, "data.json %s" % i)
        time.sleep(float(random.randint(1, 100)) / 100)
    print "Done"

    print "Testing cleanup"
    thread = callAsync("publish content.json single", 1, publish, "content.json single")
    print "Needs to cleanup:", called_db, queue_db
    print "Waiting 3min for cleanup process..."
    time.sleep(60 * 3)
    print "Cleaned up:", called_db, queue_db
