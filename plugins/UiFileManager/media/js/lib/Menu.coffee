class Menu
	constructor: ->
		@visible = false
		@items = []
		@node = null
		@height = 0
		@direction = "bottom"

	show: =>
		window.visible_menu?.hide()
		@visible = true
		window.visible_menu = @
		@direction = @getDirection()

	hide: =>
		@visible = false

	toggle: =>
		if @visible
			@hide()
		else
			@show()
		Page.projector.scheduleRender()


	addItem: (title, cb, selected=false) ->
		@items.push([title, cb, selected])


	storeNode: (node) =>
		@node = node
		# Animate visible
		if @visible
			node.className = node.className.replace("visible", "")
			setTimeout (=>
				node.className += " visible"
				node.attributes.style.value = @getStyle()
			), 20
			node.style.maxHeight = "none"
			@height = node.offsetHeight
			node.style.maxHeight = "0px"
			@direction = @getDirection()

	getDirection: =>
		if @node and @node.parentNode.getBoundingClientRect().top + @height + 60 > document.body.clientHeight and @node.parentNode.getBoundingClientRect().top - @height > 0
			return "top"
		else
			return "bottom"

	handleClick: (e) =>
		keep_menu = false
		for item in @items
			[title, cb, selected] = item
			if title == e.currentTarget.textContent or e.currentTarget["data-title"] == title
				keep_menu = cb?(item)
				break
		if keep_menu != true and cb != null
			@hide()
		return false

	renderItem: (item) =>
		[title, cb, selected] = item
		if typeof(selected) == "function"
			selected = selected()

		if title == "---"
			return h("div.menu-item-separator", {key: Time.timestamp()})
		else
			if cb == null
				href = undefined
				onclick = @handleClick
			else if typeof(cb) == "string"  # Url
				href = cb
				onclick = true
			else  # Callback
				href = "#"+title
				onclick = @handleClick
			classes = {
				"selected": selected,
				"noaction": (cb == null)
			}
			return h("a.menu-item", {href: href, onclick: onclick, "data-title": title, key: title, classes: classes}, title)

	getStyle: =>
		if @visible
			max_height = @height
		else
			max_height = 0
		style = "max-height: #{max_height}px"
		if @direction == "top"
			style += ";margin-top: #{0 - @height - 50}px"
		else
			style += ";margin-top: 0px"
		return style

	render: (class_name="") =>
		if @visible or @node
			h("div.menu#{class_name}", {classes: {"visible": @visible}, style: @getStyle(), afterCreate: @storeNode}, @items.map(@renderItem))

window.Menu = Menu

# Hide menu on outside click
document.body.addEventListener "mouseup", (e) ->
	if not window.visible_menu or not window.visible_menu.node
		return false
	menu_node = window.visible_menu.node
	menu_parents = [menu_node, menu_node.parentNode]
	if e.target.parentNode not in menu_parents and e.target.parentNode.parentNode not in menu_parents
		window.visible_menu.hide()
		Page.projector.scheduleRender()
