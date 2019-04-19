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
			if not value.length
				return value = null
			else
				return value.split("\n")
		if type == "boolean" and not value
			return false
		else
			return value

	createSections: ->
		# Web Interface
		section = @createSection("Web Interface")

		section.items.push
			key: "open_browser"
			title: "Open web browser on ZeroNet startup"
			type: "checkbox"

		# Network
		section = @createSection("Network")
		section.items.push
			key: "offline"
			title: "Offline mode"
			type: "checkbox"
			description: "Disable network communication."

		section.items.push
			key: "fileserver_ip_type"
			title: "File server network"
			type: "select"
			options: [
				{title: "IPv4", value: "ipv4"}
				{title: "IPv6", value: "ipv6"}
				{title: "Dual (IPv4 & IPv6)", value: "dual"}
			]
			description: "Accept incoming peers using IPv4 or IPv6 address. (default: dual)"

		section.items.push
			key: "fileserver_port"
			title: "File server port"
			type: "text"
			valid_pattern: /[0-9]*/
			description: "Other peers will use this port to reach your served sites. (default: 15441)"

		section.items.push
			key: "ip_external"
			title: "File server external ip"
			type: "textarea"
			placeholder: "Detect automatically"
			description: "Your file server is accessible on these ips. (default: detect automatically)"

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
			isHidden: ->
				return not Page.server_info.tor_has_meek_bridges

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

		# Performance
		section = @createSection("Performance")

		section.items.push
			key: "log_level"
			title: "Level of logging to file"
			type: "select"
			options: [
				{title: "Everything", value: "DEBUG"}
				{title: "Only important messages", value: "INFO"}
				{title: "Only errors", value: "ERROR"}
			]

	createSection: (title) =>
		section = {}
		section.title = title
		section.items = []
		@items.push(section)
		return section

window.ConfigStorage = ConfigStorage