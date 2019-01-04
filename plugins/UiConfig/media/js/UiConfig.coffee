window.h = maquette.h

class UiConfig extends ZeroFrame
	init: ->
		@save_visible = true
		@config = null  # Setting currently set on the server
		@values = null  # Entered values on the page
		@config_view = new ConfigView()
		window.onbeforeunload = =>
			if @getValuesChanged().length > 0
				return true
			else
				return null

	onOpenWebsocket: =>
		@cmd("wrapperSetTitle", "Config - ZeroNet")
		@cmd "serverInfo", {}, (server_info) =>
			@server_info = server_info
		@restart_loading = false
		@updateConfig()

	updateConfig: (cb) =>
		@cmd "configList", [], (res) =>
			@config = res
			@values = {}
			@config_storage = new ConfigStorage(@config)
			@config_view.values = @values
			@config_view.config_storage = @config_storage
			for key, item of res
				value = item.value
				@values[key] = @config_storage.formatValue(value)
			@projector.scheduleRender()
			cb?()

	createProjector: =>
		@projector = maquette.createProjector()
		@projector.replace($("#content"), @render)
		@projector.replace($("#bottom-save"), @renderBottomSave)
		@projector.replace($("#bottom-restart"), @renderBottomRestart)

	getValuesChanged: =>
		values_changed = []
		for key, value of @values
			if @config_storage.formatValue(value) != @config_storage.formatValue(@config[key]?.value)
				values_changed.push({key: key, value: value})
		return values_changed

	getValuesPending: =>
		values_pending = []
		for key, item of @config
			if item.pending
				values_pending.push(key)
		return values_pending

	saveValues: (cb) =>
		changed_values = @getValuesChanged()
		for item, i in changed_values
			last = i == changed_values.length - 1
			value = @config_storage.deformatValue(item.value, typeof(@config[item.key].default))
			value_same_as_default = JSON.stringify(@config[item.key].default) == JSON.stringify(value)
			if value_same_as_default
				value = null

			if @config[item.key].item.valid_pattern and not @config[item.key].item.isHidden?()
				match = value.match(@config[item.key].item.valid_pattern)
				if not match or match[0] != value
					message = "Invalid value of #{@config[item.key].item.title}: #{value} (does not matches #{@config[item.key].item.valid_pattern})"
					Page.cmd("wrapperNotification", ["error", message])
					cb(false)
					break

			@saveValue(item.key, value, if last then cb else null)

	saveValue: (key, value, cb) =>
		if key == "open_browser"
			if value
				value = "default_browser"
			else
				value = "False"

		Page.cmd "configSet", [key, value], (res) =>
			if res != "ok"
				Page.cmd "wrapperNotification", ["error", res.error]
			cb?(true)

	render: =>
		if not @config
			return h("div.content")

		h("div.content", [
			@config_view.render()
		])

	handleSaveClick: =>
		@save_loading = true
		@logStart "Save"
		@saveValues (success) =>
			@save_loading = false
			@logEnd "Save"
			if success
				@updateConfig()
			Page.projector.scheduleRender()
		return false

	renderBottomSave: =>
		values_changed = @getValuesChanged()
		h("div.bottom.bottom-save", {classes: {visible: values_changed.length}}, h("div.bottom-content", [
			h("div.title", "#{values_changed.length} configuration item value changed"),
			h("a.button.button-submit.button-save", {href: "#Save", classes: {loading: @save_loading}, onclick: @handleSaveClick}, "Save settings")
		]))

	handleRestartClick: =>
		@restart_loading = true
		Page.cmd("serverShutdown", {restart: true})
		Page.projector.scheduleRender()
		return false

	renderBottomRestart: =>
		values_pending = @getValuesPending()
		values_changed = @getValuesChanged()
		h("div.bottom.bottom-restart", {classes: {visible: values_pending.length and not values_changed.length}}, h("div.bottom-content", [
			h("div.title", "Some changed settings requires restart"),
			h("a.button.button-submit.button-restart", {href: "#Restart", classes: {loading: @restart_loading}, onclick: @handleRestartClick}, "Restart ZeroNet client")
		]))

window.Page = new UiConfig()
window.Page.createProjector()
