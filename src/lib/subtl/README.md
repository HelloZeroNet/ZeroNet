# subtl

## Overview

SUBTL is a **s**imple **U**DP **B**itTorrent **t**racker **l**ibrary for Python, licenced under the modified BSD license.

## Example

This short example will list a few IP Addresses from a certain hash:

    from subtl import UdpTrackerClient
    utc = UdpTrackerClient('tracker.openbittorrent.com', 80)
    utc.connect()
    if not utc.poll_once():
        raise Exception('Could not connect')
    print('Success!')

    utc.announce(info_hash='089184ED52AA37F71801391C451C5D5ADD0D9501')
    data = utc.poll_once()
    if not data:
        raise Exception('Could not announce')
    for a in data['response']['peers']:
        print(a)

## Caveats

 * There is no automatic retrying of sending packets yet.
 * This library won't download torrent files--it is simply a tracker client.
