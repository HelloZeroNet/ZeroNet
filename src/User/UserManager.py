import json, logging, os
from User import User

users = None

# Load all user from data/users.json
def load():
	global users
	if not users: users = {}

	user_found = []
	added = 0
	# Load new users
	for master_address, data in json.load(open("data/users.json")).items():
		if master_address not in users:
			user = User(master_address)
			user.setData(data)
			users[master_address] = user
			added += 1
		user_found.append(master_address)

	# Remove deleted adresses
	for master_address in users.keys():
		if master_address not in user_found: 
			del(users[master_address])
			logging.debug("Removed user: %s" % master_address)

	if added: logging.debug("UserManager added %s users" % added)


# Create new user
# Return: User
def create():
	user = User()
	logging.debug("Created user: %s" % user.master_address)
	users[user.master_address] = user
	user.save()
	return user


# List all users from data/users.json
# Return: {"usermasteraddr": User}
def list():
	if users == None: # Not loaded yet
		load()
	return users


# Get current authed user
# Return: User
def getCurrent():
	users = list()
	if users:
		return users.values()[0]
	else:
		return create()


# Debug: Reload User.py
def reload():
	import imp
	global users, User
	User = imp.load_source("User", "src/User/User.py").User # Reload source
	users.clear() # Remove all items
	load()
