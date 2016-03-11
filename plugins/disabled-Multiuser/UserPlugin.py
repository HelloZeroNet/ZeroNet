from Config import config
from Plugin import PluginManager

allow_reload = False

@PluginManager.registerTo("UserManager")
class UserManagerPlugin(object):
    def load(self):
        if not config.multiuser_local:
            # In multiuser mode do not load the users
            if not self.users:
                self.users = {}
            return self.users
        else:
            return super(UserManagerPlugin, self).load()

    # Find user by master address
    # Return: User or None
    def get(self, master_address=None):
        users = self.list()
        if master_address in users:
            user = users[master_address]
        else:
            user = None
        return user


@PluginManager.registerTo("User")
class UserPlugin(object):
    # In multiuser mode users data only exits in memory, dont write to data/user.json
    def save(self):
        if not config.multiuser_local:
            return False
        else:
            return super(UserPlugin, self).save()
