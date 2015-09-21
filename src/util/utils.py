import os


def atomicWrite(dest, content, mode="w"):
    open(dest + "-new", mode).write(content)
    os.rename(dest, dest + "-old")
    os.rename(dest + "-new", dest)
    os.unlink(dest + "-old")


def shellquote(*args):
    if len(args) == 1:
        return '"%s"' % args[0].replace('"', "")
    else:
        return tuple(['"%s"' % arg.replace('"', "") for arg in args])
