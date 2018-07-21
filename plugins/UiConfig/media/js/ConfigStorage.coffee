class ConfigStorage extends Class
	constructor: (@config) ->
		@items = []
		@createSections()
		@setValues(@config)

	setValues: (values) ->
		for section in @items
			for item in section.items
				if not values[item.key]
					continue
				item.value = @formatValue(values[item.key].value)
				item.default = @formatValue(values[item.key].default)
				item.pending = values[item.key].pending
				values[item.key].item = item

	formatValue: (value) ->
		if not value
			return false
		else if typeof(value) == "object"
			return value.join("\n")
		else if typeof(value) == "number"
			return value.toString()
		else
			return value

	deformatValue: (value, type) ->
		if type == "object" and typeof(value) == "string"
			return value.split("\n")
		if type == "boolean" and not value
			return false
		else
			return value

	createSections: ->
		section = @createSection("Web Interface")

		# Web Interface
		section.items.push
			key: "open_browser"
			title: "Open web browser on ZeroNet startup"
			type: "checkbox"

		# Network
		section = @createSection("Network")

		section.items.push
			key: "fileserver_port"
			title: "File server port"
			type: "text"
			valid_pattern: /[0-9]*/
			description: "Other peers will use this port to reach your served sites. (default: 15441)"

		section.items.push
			title: "Tor"
			key: "tor"
			type: "select"
			options: [
				{title: "Disable", value: "disable"}
				{title: "Enable", value: "enable"}
				{title: "Always", value: "always"}
			]
			description: [
				"Disable: Don't connect to peers on Tor network", h("br"),
				"Enable: Only use Tor for Tor network peers", h("br"),
				"Always: Use Tor for every connections to hide your IP address (slower)"
			]

		section.items.push
			title: "Use Tor bridges"
			key: "tor_use_bridges"
			type: "checkbox"
			description: "Use obfuscated bridge relays to avoid network level Tor block (even slower)"

		section.items.push
			title: "Trackers"
			key: "trackers"
			type: "textarea"
			description: "Discover new peers using these adresses"

		section.items.push
			title: "Trackers files"
			key: "trackers_file"
			type: "text"
			description: "Load additional list of torrent trackers dynamically, from a file"
			placeholder: "Eg.: data/trackers.json"
			value_pos: "fullwidth"

		section.items.push
			title: "Proxy for tracker connections"
			key: "trackers_proxy"
			type: "select"
			options: [
				{title: "Custom", value: ""}
				{title: "Tor", value: "tor"}
				{title: "Disable", value: "disable"}
			]

		section.items.push
			title: "Custom socks proxy address for trackers"
			key: "trackers_proxy"
			type: "text"
			placeholder: "Eg.: 127.0.0.1:1080"
			value_pos: "fullwidth"
			valid_pattern: /.+:[0-9]+/
			isHidden: =>
				Page.values["trackers_proxy"] in ["tor", "disable"]

	createSection: (title) =>
		section = {}
		section.title = title
		section.items = []
		@items.push(section)
		return section

window.ConfigStorage = ConfigStorage
