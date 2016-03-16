import re
from Plugin import PluginManager

# Warning: If you modify the donation address then renmae the plugin's directory to "MyDonationMessage" to prevent the update script overwrite


@PluginManager.registerTo("UiRequest")
class UiRequestPlugin(object):
    # Inject a donation message to every page top right corner
    def renderWrapper(self, *args, **kwargs):
        body = super(UiRequestPlugin, self).renderWrapper(*args, **kwargs)  # Get the wrapper frame output

        inject_html = """
            <style>
             #donation_message { position: absolute; bottom: 0px; right: 20px; padding: 7px; font-family: Arial; font-size: 11px }
            </style>
            <a id='donation_message' href='https://blockchain.info/address/1QDhxQ6PraUZa21ET5fYUCPgdrwBomnFgX' target='_blank'>Please donate to help to keep this ZeroProxy alive</a>
            </body>
            </html>
        """

        return re.sub("</body>\s*</html>\s*$", inject_html, body)
