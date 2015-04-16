import re
from Plugin import PluginManager

# Warning: If you modify the donation address then renmae the plugin's directory to "MyDonationMessage" to prevent the update script overwrite


@PluginManager.registerTo("UiRequest")
class UiRequestPlugin(object):
	# Inject a donation message to every page top right corner
	def actionWrapper(self, path):
		back = super(UiRequestPlugin, self).actionWrapper(path)
		if not back or not hasattr(back, "endswith"): return back # Wrapper error or not string returned, injection not possible

		back = re.sub("</body>\s*</html>\s*$", 
			"""
			<style>
			 #donation_message { position: absolute; bottom: 0px; right: 20px; padding: 7px; font-family: Arial; font-size: 11px }
			</style>
			<a id='donation_message' href='https://blockchain.info/address/1QDhxQ6PraUZa21ET5fYUCPgdrwBomnFgX' target='_blank'>Please donate to help to keep this ZeroProxy alive</a>
			</body>
			</html>
			""", back)

		return back
