class ConfigView extends Class
	constructor: () ->
		@

	render: ->
		@config_storage.items.map @renderSection

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

		if item.isHidden?()
			return null

		h("div.config-item", {key: item.title, enterAnimation: Animation.slideDown, exitAnimation: Animation.slideUpInout}, [
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
			type: item.type, config_key: item.key, oninput: @handleInputChange, afterCreate: @autosizeTextarea,
			updateAnimation: @autosizeTextarea, value: value, placeholder: item.placeholder
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

window.ConfigView = ConfigView