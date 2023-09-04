class PluginList extends Class
	constructor: (plugins) ->
		@plugins = plugins

	savePluginStatus: (plugin, is_enabled) =>
		Page.cmd "pluginConfigSet", [plugin.source, plugin.inner_path, "enabled", is_enabled], (res) =>
			if res == "ok"
				Page.updatePlugins()
			else
				Page.cmd "wrapperNotification", ["error", res.error]

		Page.projector.scheduleRender()

	handleCheckboxChange: (e) =>
		node = e.currentTarget
		plugin = node["data-plugin"]
		node.classList.toggle("checked")
		value = node.classList.contains("checked")

		@savePluginStatus(plugin, value)

	handleResetClick: (e) =>
		node = e.currentTarget
		plugin = node["data-plugin"]

		@savePluginStatus(plugin, null)

	handleUpdateClick: (e) =>
		node = e.currentTarget
		plugin = node["data-plugin"]
		node.classList.add("loading")

		Page.cmd "pluginUpdate", [plugin.source, plugin.inner_path], (res) =>
			if res == "ok"
				Page.cmd "wrapperNotification", ["done", "Plugin #{plugin.name} updated to latest version"]
				Page.updatePlugins()
			else
				Page.cmd "wrapperNotification", ["error", res.error]
			node.classList.remove("loading")

		return false

	handleDeleteClick: (e) =>
		node = e.currentTarget
		plugin = node["data-plugin"]
		if plugin.loaded
			Page.cmd "wrapperNotification", ["info", "You can only delete plugin that are not currently active"]
			return false

		node.classList.add("loading")

		Page.cmd "wrapperConfirm", ["Delete #{plugin.name} plugin?", "Delete"], (res) =>
			if not res
				node.classList.remove("loading")
				return false

			Page.cmd "pluginRemove", [plugin.source, plugin.inner_path], (res) =>
				if res == "ok"
					Page.cmd "wrapperNotification", ["done", "Plugin #{plugin.name} deleted"]
					Page.updatePlugins()
				else
					Page.cmd "wrapperNotification", ["error", res.error]
				node.classList.remove("loading")

		return false

	render: ->
		h("div.plugins", @plugins.map (plugin) =>
			if not plugin.info
				return
			descr = plugin.info.description
			plugin.info.default ?= "enabled"
			if plugin.info.default
				descr += " (default: #{plugin.info.default})"

			tag_version = ""
			tag_source = ""
			tag_delete = ""
			if plugin.source != "builtin"
				tag_update = ""
				if plugin.site_info?.rev
					if plugin.site_info.rev > plugin.info.rev
						tag_update = h("a.version-update.button",
							{href: "#Update+plugin", onclick: @handleUpdateClick, "data-plugin": plugin},
							"Update to rev#{plugin.site_info.rev}"
						)

				else
					tag_update = h("span.version-missing", "(unable to get latest vesion: update site missing)")

				tag_version = h("span.version",[
					"rev#{plugin.info.rev} ",
					tag_update,
				])

				tag_source = h("div.source",[
					"Source: ",
					h("a", {"href": "/#{plugin.source}", "target": "_top"}, if plugin.site_title then plugin.site_title else plugin.source),
					" /" + plugin.inner_path
				])

				tag_delete = h("a.delete", {"href": "#Delete+plugin", onclick: @handleDeleteClick, "data-plugin": plugin}, "Delete plugin")


			enabled_default = plugin.info.default == "enabled"
			if plugin.enabled != plugin.loaded or plugin.updated
				marker_title = "Change pending"
				is_pending = true
			else
				marker_title = "Changed from default status (click to reset to #{plugin.info.default})"
				is_pending = false

			is_changed = plugin.enabled != enabled_default and plugin.owner == "builtin"

			h("div.plugin", {key: plugin.name}, [
				h("div.title", [
					h("h3", [plugin.name, tag_version]),
					h("div.description", [descr, tag_source, tag_delete]),
				])
				h("div.value.value-right",
					h("div.checkbox", {onclick: @handleCheckboxChange, "data-plugin": plugin, classes: {checked: plugin.enabled}}, h("div.checkbox-skin"))
				h("a.marker", {
					href: "#Reset", title: marker_title,
					onclick: @handleResetClick, "data-plugin": plugin,
					classes: {visible: is_pending or is_changed, pending: is_pending}
				}, "\u2022")
				)
			])
		)


window.PluginList = PluginList