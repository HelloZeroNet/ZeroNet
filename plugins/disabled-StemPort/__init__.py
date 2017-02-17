try:
    from stem.control import Controller
    stem_found = True
except Exception, err:
    print "STEM NOT FOUND! %s" % err
    stem_found = False

if stem_found:
    print "Starting Stem plugin..."
    import StemPortPlugin
