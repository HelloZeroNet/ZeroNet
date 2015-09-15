import os

def atomicWrite(dest, content, mode="w"):
    open(dest+"-new", mode).write(content)
    os.rename(dest, dest+"-old")
    os.rename(dest+"-new", dest)
    os.unlink(dest+"-old")
