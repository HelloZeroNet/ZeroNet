import re, time, sys
from Plugin import PluginManager
from Crypt import CryptBitcoin

@PluginManager.registerTo("UiRequest")
class UiRequestPlugin(object):
	def __init__(self, *args, **kwargs):
		self.user_manager = sys.modules["User.UserManager"].user_manager
		super(UiRequestPlugin, self).__init__(*args, **kwargs)


	# Create new user and inject user welcome message if necessary
	# Return: Html body also containing the injection
	def actionWrapper(self, path):
		user_created = False
		user = self.getCurrentUser() # Get user from cookie

		if not user: # No user found by cookie
			user = self.user_manager.create()
			user_created = True

		master_address = user.master_address
		master_seed = user.master_seed

		if user_created: 
			extra_headers = [('Set-Cookie', "master_address=%s;path=/;max-age=2592000;" % user.master_address)] # Max age = 30 days
		else:
			extra_headers = []

		loggedin = self.get.get("login") == "done"

		back = super(UiRequestPlugin, self).actionWrapper(path, extra_headers) # Get the wrapper frame output

		if not user_created and not loggedin: return back # No injection necessary

		if not back or not hasattr(back, "endswith"): return back # Wrapper error or not string returned, injection not possible

		if user_created:
			# Inject the welcome message
			inject_html = """
				<!-- Multiser plugin -->
				<style>
	 			 .masterseed { font-size: 95%; background-color: #FFF0AD; padding: 5px 8px; margin: 9px 0px }
				</style>
				<script>
				 hello_message = "<b>Hello, welcome to ZeroProxy!</b><div style='margin-top: 8px'>A new, unique account created for you:</div>"
				 hello_message+= "<div class='masterseed'>{master_seed}</div> <div>This is your private key, <b>save it</b>, so you can login next time.</div><br>"
				 hello_message+= "<a href='#' class='button' style='margin-left: 0px'>Ok, Saved it!</a> or <a href='#Login' onclick='wrapper.ws.cmd(\\"userLoginForm\\", []); return false'>Login</a><br><br>"
				 hello_message+= "<small>This site is allows you to browse ZeroNet content, but if you want to secure your account <br>"
				 hello_message+= "and help to make a better network, then please run your own <a href='https://github.com/HelloZeroNet/ZeroNet' target='_blank'>ZeroNet client</a>.</small>"
				 setTimeout(function() {
				 	wrapper.notifications.add("hello", "info", hello_message)
				 	delete(hello_message)
				 }, 1000)
				</script>
				</body>
				</html>
			""".replace("\t", "")
			inject_html = inject_html.replace("{master_seed}", master_seed) # Set the master seed in the message

			back = re.sub("</body>\s*</html>\s*$", inject_html, back) # Replace the </body></html> tags with the injection 

		elif loggedin:
			inject_html = """
				<!-- Multiser plugin -->
				<script>
				 setTimeout(function() {
				 	wrapper.notifications.add("login", "done", "Hello again!<br><small>You have been logged in successfully</small>", 5000) 
				 }, 1000)
				</script>
				</body>
				</html>
			""".replace("\t", "")
			back = re.sub("</body>\s*</html>\s*$", inject_html, back) # Replace the </body></html> tags with the injection

		return back 


	# Get the current user based on request's cookies
	# Return: User object or None if no match
	def getCurrentUser(self):
		cookies = self.getCookies()
		user_manager = self.user_manager
		user = None
		if "master_address" in cookies:
			users = self.user_manager.list()
			user = users.get(cookies["master_address"])
		return user


@PluginManager.registerTo("UserManager")
class UserManagerPlugin(object):
	# In multiuser mode do not load the users
	def load(self):
		if not self.users: self.users = {}
		return self.users


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
		return False 
 

@PluginManager.registerTo("UiWebsocket")
class UiWebsocketPlugin(object):
	# Let the page know we running in multiuser mode
	def formatServerInfo(self):
		server_info = super(UiWebsocketPlugin, self).formatServerInfo()
		server_info["multiuser"] = True
		if "ADMIN" in self.site.settings["permissions"]:
			server_info["master_address"] = self.user.master_address
		return server_info


	# Show current user's master seed
	def actionUserShowMasterSeed(self, to):
		if not "ADMIN" in self.site.settings["permissions"]: return self.response(to, "Show master seed not allowed")
		message = "<b style='padding-top: 5px; display: inline-block'>Your unique private key:</b>"
		message+= "<div style='font-size: 84%%; background-color: #FFF0AD; padding: 5px 8px; margin: 9px 0px'>%s</div>" % self.user.master_seed
		message+= "<small>(Save it, you can access your account using this information)</small>"
		self.cmd("notification", ["info", message])


	# Logout user
	def actionUserLogout(self, to):
		if not "ADMIN" in self.site.settings["permissions"]: return self.response(to, "Logout not allowed")
		message = "<b>You have been logged out.</b> <a href='#Login' class='button' onclick='wrapper.ws.cmd(\"userLoginForm\", []); return false'>Login to another account</a>"
		message+= "<script>document.cookie = 'master_address=; expires=Thu, 01 Jan 1970 00:00:00 UTC'</script>"
		self.cmd("notification", ["done", message, 1000000]) # 1000000 = Show ~forever :)
		# Delete from user_manager
		user_manager = sys.modules["User.UserManager"].user_manager
		if self.user.master_address in user_manager.users:
			del user_manager.users[self.user.master_address]
			self.response(to, "Successful logout")
		else:
			self.response(to, "User not found")


	# Show login form
	def actionUserLoginForm(self, to):
		self.cmd("prompt", ["<b>Login</b><br>Your private key:", "password", "Login"], self.responseUserLogin)


	# Login form submit
	def responseUserLogin(self, master_seed):
		user_manager = sys.modules["User.UserManager"].user_manager
		user = user_manager.create(master_seed=master_seed)
		if user.master_address:
			message = "Successfull login, reloading page..."
			message+= "<script>document.cookie = 'master_address=%s;path=/;max-age=2592000;'</script>" % user.master_address
			message+= "<script>wrapper.reload('login=done')</script>"
			self.cmd("notification", ["done", message])
		else:
			self.cmd("notification", ["error", "Error: Invalid master seed"])
			self.actionUserLoginForm(0)

