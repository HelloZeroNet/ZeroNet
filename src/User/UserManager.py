# Included modules
import json
import logging

# ZeroNet Modules
from User import User
from Plugin import PluginManager
from Config import config


@PluginManager.acceptPlugins
class UserManager(object):
    def __init__(self):
        self.users = {}

    # Load all user from data/users.json
    def load(self):
        if not self.users:
            self.users = {}

        user_found = []
        added = 0
        # Load new users
        for master_address, data in json.load(open("%s/users.json" % config.data_dir)).items():
            if master_address not in self.users:
                user = User(master_address, data=data)
                self.users[master_address] = user
                added += 1
            user_found.append(master_address)

        # Remove deleted adresses
        for master_address in self.users.keys():
            if master_address not in user_found:
                del(self.users[master_address])
                logging.debug("Removed user: %s" % master_address)

        if added:
            logging.debug("UserManager added %s users" % added)

    # Create new user
    # Return: User
    def create(self, master_address=None, master_seed=None):
        user = User(master_address, master_seed)
        logging.debug("Created user: %s" % user.master_address)
        if user.master_address:  # If successfully created
            self.users[user.master_address] = user
            user.save()
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
            return users.values()[0]  # Single user mode, always return the first
        else:
            return None


user_manager = UserManager()  # Singleton


# Debug: Reload User.py
def reloadModule():
    return "Not used"

    import imp
    global User, UserManager, user_manager
    User = imp.load_source("User", "src/User/User.py").User  # Reload source
    # module = imp.load_source("UserManager", "src/User/UserManager.py") # Reload module
    # UserManager = module.UserManager
    # user_manager = module.user_manager
    # Reload users
    user_manager = UserManager()
    user_manager.load()
