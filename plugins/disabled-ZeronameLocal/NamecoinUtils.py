import os, signal, json, requests, subprocess, time
from pathlib import Path
from configparser import ConfigParser
import psutil


def is_namecoin_installed():
    home = str(Path.home())
    dot_namecoin = os.path.join(home, '.namecoin')
    is_dot_namecoin = os.path.exists(dot_namecoin)
    return is_dot_namecoin


def is_namecoin_running():
    for proc in psutil.process_iter(['pid', 'name', 'username']):
        if "namecoin" in proc.name():
            return proc


def get_namecoin_conf():
    namecoin_conf = os.path.join(str(Path.home()), '.namecoin', 'namecoin.conf')
    parser = ConfigParser()
    with open(namecoin_conf) as stream:
        parser.read_string("[fake-section]\n" + stream.read())
        config = dict(parser.items('fake-section'))
        return config


def check_namecoin_rpc_conf(config):
    if None in (config['rpcconnect'], config['rpcport'], config['rpcuser'], config['rpcpassword']):
        return False
    else:
        return True


def start_namecoin(path):
    process = subprocess.Popen(["{}namecoind".format(path)])
    return process.pid


def kill_namecoin(pid):
    os.kill(pid, signal.SIGTERM)
    return True
