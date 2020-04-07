import gevent
from Debug import Debug


class GreenletManager:
    def __init__(self):
        self.greenlets = set()

    def spawnLater(self, *args, **kwargs):
        greenlet = gevent.spawn_later(*args, **kwargs)
        greenlet.link(lambda greenlet: self.greenlets.remove(greenlet))
        self.greenlets.add(greenlet)
        return greenlet

    def spawn(self, *args, **kwargs):
        greenlet = gevent.spawn(*args, **kwargs)
        greenlet.link(lambda greenlet: self.greenlets.remove(greenlet))
        self.greenlets.add(greenlet)
        return greenlet

    def stopGreenlets(self, reason="Stopping all greenlets"):
        num = len(self.greenlets)
        gevent.killall(list(self.greenlets), Debug.Notify(reason), block=False)
        return num
