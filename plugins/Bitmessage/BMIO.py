from base64 import b64encode

from BMAPI import BMAPI

def sendMessage(sender, recipient, subject, body):
    ackData = BMAPI().conn().sendMessage(recipient, sender, b64encode(subject), b64encode(body), 2)
    return ackData
