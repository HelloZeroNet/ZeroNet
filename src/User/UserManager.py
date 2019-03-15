# Included modules
import json
import logging
import time

# ZeroNet Modules
from .User import User
from Plugin import PluginManager
from Config import config


@PluginManager.acceptPlugins
class UserManager(object):
    def __init__(self):
        self.users = {}
        self.log = logging.getLogger("UserManager")

    # Load all user from data/users.json
    def load(self):
        if not self.users:
            self.users = {}

        user_found = []
        added = 0
        s = time.time()
        # Load new users
        for master_address, data in list(json.load(open("%s/users.json" % config.data_dir)).items()):
            if master_address not in self.users:
                user = User(master_address, data=data)
                self.users[master_address] = user
                added += 1
            user_found.append(master_address)

        # Remove deleted adresses
        for master_address in list(self.users.keys()):
            if master_address not in user_found:
                del(self.users[master_address])
                self.log.debug("Removed user: %s" % master_address)

        if added:
            self.log.debug("Added %s users in %.3fs" % (added, time.time() - s))

    # Create new user
    # Return: User
    def create(self, master_address=None, master_seed=None):
        self.list()  # Load the users if it's not loaded yet
        user = User(master_address, master_seed)
        self.log.debug("Created user: %s" % user.master_address)
        if user.master_address:  # If successfully created
            self.users[user.master_address] = user
            user.saveDelayed()
        return user

    # List all users from data/users.json
    # Return: {"usermasteraddr": User}
    def list(self):
        if self.users == {}:  # Not loaded yet
            self.load()
        return self.users

    # Get user based on master_address
    # Return: User or None
    def get(self, master_address=None):
        users = self.list()
        if users:
            return list(users.values())[0]  # Single user mode, always return the first
        else:
            return None


user_manager = UserManager()  # Singleton
