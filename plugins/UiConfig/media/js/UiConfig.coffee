window.h = maquette.h

class UiConfig extends ZeroFrame
	init: ->
		@save_visible = true
		@config = null  # Setting currently set on the server
		@values = null  # Entered values on the page
		window.onbeforeunload = =>
			if @getValuesChanged().length > 0
				return true
			else
				return null

	onOpenWebsocket: =>
		@cmd("wrapperSetTitle", "Config - ZeroNet")
		@updateConfig()

	updateConfig: (cb) =>
		@cmd "configList", [], (res) =>
			@config = res
			@values = {}
			@config_storage = new ConfigStorage(@config)
			for key, item of res
				@values[key] = @config_storage.formatValue(item.value)
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
			if @config_storage.formatValue(value) != @config_storage.formatValue(@config[key].value)
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
			cb?()

	renderSection: (section) =>
		h("div.section", {key: section.title}, [
			h("h2", section.title),
			h("div.config-items", section.items.map @renderSectionItem)
		])

	handleResetClick: (e) =>
		node = e.currentTarget
		config_key = node.attributes.config_key.value
		default_value = node.attributes.default_value?.value
		Page.cmd "wrapperConfirm", ["Reset #{config_key} value?", "Reset to default"], (res) =>
			if (res)
				@values[config_key] = default_value
			Page.projector.scheduleRender()

	renderSectionItem: (item) =>
		value_pos = item.value_pos

		if item.type == "textarea"
			value_pos ?= "fullwidth"
		else
			value_pos ?= "right"

		value_changed = @config_storage.formatValue(@values[item.key]) != item.value
		value_default = @config_storage.formatValue(@values[item.key]) == item.default

		if item.key in ["open_browser", "fileserver_port"]  # Value default for some settings makes no sense
			value_default = true

		marker_title = "Changed from default value: #{item.default} -> #{@values[item.key]}"
		if item.pending
			marker_title += " (change pending until client restart)"

		h("div.config-item", [
			h("div.title", [
				h("h3", item.title),
				h("div.description", item.description)
			])
			h("div.value.value-#{value_pos}",
				if item.type == "select"
					@renderValueSelect(item)
				else if item.type == "checkbox"
					@renderValueCheckbox(item)
				else if item.type == "textarea"
					@renderValueTextarea(item)
				else
					@renderValueText(item)
				h("a.marker", {
					href: "#Reset", title: marker_title,
					onclick: @handleResetClick, config_key: item.key, default_value: item.default,
					classes: {default: value_default, changed: value_changed, visible: not value_default or value_changed or item.pending, pending: item.pending}
				}, "\u2022")
			)
		])

	# Values
	handleInputChange: (e) =>
		node = e.target
		config_key = node.attributes.config_key.value
		@values[config_key] = node.value
		Page.projector.scheduleRender()

	handleCheckboxChange: (e) =>
		node = e.currentTarget
		config_key = node.attributes.config_key.value
		value = not node.classList.contains("checked")
		@values[config_key] = value
		Page.projector.scheduleRender()

	renderValueText: (item) =>
		value = @values[item.key]
		if not value
			value = ""
		h("input.input-#{item.type}", {type: item.type, config_key: item.key, value: value, placeholder: item.placeholder, oninput: @handleInputChange})

	autosizeTextarea: (e) =>
		@log "autosize", arguments
		if e.currentTarget
			# @handleInputChange(e)
			node = e.currentTarget
		else
			node = e
		height_before = node.style.height
		if height_before
			node.style.height = "0px"
		h = node.offsetHeight
		scrollh = node.scrollHeight + 20
		if scrollh > h
			node.style.height = scrollh + "px"
		else
			node.style.height = height_before

	renderValueTextarea: (item) =>
		value = @values[item.key]
		if not value
			value = ""
		h("textarea.input-#{item.type}.input-text",{
			type: item.type, config_key: item.key, oninput: @handleInputChange, afterCreate: @autosizeTextarea, updateAnimation: @autosizeTextarea, value: value
		})

	renderValueCheckbox: (item) =>
		if @values[item.key] and @values[item.key] != "False"
			checked = true
		else
			checked = false
		h("div.checkbox", {onclick: @handleCheckboxChange, config_key: item.key, classes: {checked: checked}}, h("div.checkbox-skin"))

	renderValueSelect: (item) =>
		h("select.input-select", {config_key: item.key, oninput: @handleInputChange},
			item.options.map (option) =>
				h("option", {selected: option.value == @values[item.key], value: option.value}, option.title)
		)

	render: =>
		if not @config
			return h("div.content")

		h("div.content", [
			@config_storage.items.map @renderSection
		])

	handleSaveClick: =>
		@save_loading = true
		@logStart "Save"
		@saveValues =>
			@save_loading = false
			@logEnd "Save"
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
			h("div.title", "Some changes settings requires restart"),
			h("a.button.button-submit.button-restart", {href: "#Restart", classes: {loading: @restart_loading}, onclick: @handleRestartClick}, "Restart ZeroNet client")
		]))

window.Page = new UiConfig()
window.Page.createProjector()
