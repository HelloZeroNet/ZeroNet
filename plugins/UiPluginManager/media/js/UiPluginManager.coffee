window.h = maquette.h

class UiPluginManager extends ZeroFrame
	init: ->
		@plugin_list_builtin = new PluginList()
		@plugin_list_custom = new PluginList()
		@plugins_changed = null
		@need_restart = null
		@

	onOpenWebsocket: =>
		@cmd("wrapperSetTitle", "Plugin manager - ZeroNet")
		@cmd "serverInfo", {}, (server_info) =>
			@server_info = server_info
		@updatePlugins()

	updatePlugins: (cb) =>
		@cmd "pluginList", [], (res) =>
			@plugins_changed = (item for item in res.plugins when item.enabled != item.loaded or item.updated)

			plugins_builtin = (item for item in res.plugins when item.source == "builtin")
			@plugin_list_builtin.plugins = plugins_builtin.sort (a, b) ->
				return a.name.localeCompare(b.name)

			plugins_custom = (item for item in res.plugins when item.source != "builtin")
			@plugin_list_custom.plugins = plugins_custom.sort (a, b) ->
				return a.name.localeCompare(b.name)

			@projector.scheduleRender()
			cb?()

	createProjector: =>
		@projector = maquette.createProjector()
		@projector.replace($("#content"), @render)
		@projector.replace($("#bottom-restart"), @renderBottomRestart)

	render: =>
		if not @plugin_list_builtin.plugins
			return h("div.content")

		h("div.content", [
			h("div.section", [
				if @plugin_list_custom.plugins?.length
					[
						h("h2", "Installed third-party plugins"),
						@plugin_list_custom.render()
					]
				h("h2", "Built-in plugins")
				@plugin_list_builtin.render()
			])
		])

	handleRestartClick: =>
		@restart_loading = true
		setTimeout ( =>
			Page.cmd("serverShutdown", {restart: true})
		), 300
		Page.projector.scheduleRender()
		return false

	renderBottomRestart: =>
		h("div.bottom.bottom-restart", {classes: {visible: @plugins_changed?.length}}, h("div.bottom-content", [
			h("div.title", "Some plugins status has been changed"),
			h("a.button.button-submit.button-restart",
				{href: "#Restart", classes: {loading: @restart_loading}, onclick: @handleRestartClick},
				"Restart ZeroNet client"
			)
		]))

window.Page = new UiPluginManager()
window.Page.createProjector()
