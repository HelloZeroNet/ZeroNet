#!/bin/bash
cmd="pip2"
hash pip2 2>/dev/null || cmd="pip"
sudo $cmd install -r requirements.txt
