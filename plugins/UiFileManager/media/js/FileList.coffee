BINARY_EXTENSIONS = ["png", "gif", "jpg", "pdf", "doc", "msgpack", "zip", "rar", "gz", "tar", "exe", "wav", "ogg", "ogm", "oga", "ogv", "mp3"]

class FileList extends Class
	constructor: (@site, @inner_path, @is_owner=false) ->
		@need_update = true
		@error = null
		@url_root = "/list/" + @site + "/"
		if @inner_path
			@inner_path += "/"
			@url_root += @inner_path
		@log("inited", @url_root)
		@item_list = new FileItemList(@inner_path)
		@item_list.items = @item_list.items
		@menu_create = new Menu()

		@select_action = null
		@selected = {}
		@selected_items_num = 0
		@selected_items_size = 0
		@selected_optional_empty_num = 0

	isSelectedAll: ->
		false

	update: =>
		@item_list.update =>
			document.body.classList.add("loaded")

	getHref: (inner_path) =>
		return "/" + @site + "/" + inner_path

	getListHref: (inner_path) =>
		return "/list/" + @site + "/" + inner_path

	getEditHref: (inner_path, mode=null) =>
		href = @url_root + "?file=" + inner_path
		if mode
			href += "&edit_mode=#{mode}"
		return href

	checkSelectedItems: =>
		@selected_items_num = 0
		@selected_items_size = 0
		@selected_optional_empty_num = 0
		for item in @item_list.items
			if @selected[item.inner_path]
				@selected_items_num += 1
				@selected_items_size += item.size
				optional_info = @item_list.getOptionalInfo(item.inner_path)
				if optional_info and not optional_info.downloaded_percent > 0
					@selected_optional_empty_num += 1

	handleMenuCreateClick: =>
		@menu_create.items = []
		@menu_create.items.push ["File", @handleNewFileClick]
		@menu_create.items.push ["Directory", @handleNewDirectoryClick]
		@menu_create.toggle()
		return false

	handleNewFileClick: =>
		Page.cmd "wrapperPrompt", "New file name:", (file_name) =>
			window.top.location.href = @getEditHref(@inner_path + file_name, "new")
		return false

	handleNewDirectoryClick: =>
		Page.cmd "wrapperPrompt", "New directory name:", (res) =>
			alert("directory name #{res}")
		return false

	handleSelectClick: (e) =>
		return false

	handleSelectEnd: (e) =>
		document.body.removeEventListener('mouseup', @handleSelectEnd)
		@select_action = null

	handleSelectMousedown: (e) =>
		inner_path = e.currentTarget.attributes.inner_path.value
		if @selected[inner_path]
			delete @selected[inner_path]
			@select_action = "deselect"
		else
			@selected[inner_path] = true
			@select_action = "select"
		@checkSelectedItems()
		document.body.addEventListener('mouseup', @handleSelectEnd)
		e.stopPropagation()
		Page.projector.scheduleRender()
		return false

	handleRowMouseenter: (e) =>
		if e.buttons and @select_action
			inner_path = e.target.attributes.inner_path.value
			if @select_action == "select"
				@selected[inner_path] = true
			else
				delete @selected[inner_path]
			@checkSelectedItems()
			Page.projector.scheduleRender()
		return false

	handleSelectbarCancel: =>
		@selected = {}
		@checkSelectedItems()
		Page.projector.scheduleRender()
		return false

	handleSelectbarDelete: (e, remove_optional=false) =>
		for inner_path of @selected
			optional_info = @item_list.getOptionalInfo(inner_path)
			delete @selected[inner_path]
			if optional_info and not remove_optional
				Page.cmd "optionalFileDelete", inner_path
			else
				Page.cmd "fileDelete", inner_path
		@need_update = true
		Page.projector.scheduleRender()
		@checkSelectedItems()
		return false

	handleSelectbarRemoveOptional: (e) =>
		return @handleSelectbarDelete(e, true)

	renderSelectbar: =>
		h("div.selectbar", {classes: {visible: @selected_items_num > 0}}, [
			"Selected:",
			h("span.info", [
				h("span.num", "#{@selected_items_num} files"),
				h("span.size", "(#{Text.formatSize(@selected_items_size)})"),
			])
			h("div.actions", [
				if @selected_optional_empty_num > 0
					h("a.action.delete.remove_optional", {href: "#", onclick: @handleSelectbarRemoveOptional}, "Delete and remove optional")
				else
					h("a.action.delete", {href: "#", onclick: @handleSelectbarDelete}, "Delete")
			])
			h("a.cancel.link", {href: "#", onclick: @handleSelectbarCancel}, "Cancel")
		])

	renderHead: =>
		parent_links = []
		inner_path_parent = ""
		for parent_dir in @inner_path.split("/")
			if not parent_dir
				continue
			if inner_path_parent
				inner_path_parent += "/"
			inner_path_parent += "#{parent_dir}"
			parent_links.push(
				[" / ", h("a", {href: @getListHref(inner_path_parent)}, parent_dir)]
			)
		return h("div.tr.thead", h("div.td.full",
			h("a", {href: @getListHref("")}, "root"),
			parent_links
		))

	renderItemCheckbox: (item) =>
		if not @item_list.hasPermissionDelete(item)
			return [" "]

		return h("a.checkbox-outer", {
			href: "#Select",
			onmousedown: @handleSelectMousedown,
			onclick: @handleSelectClick,
			inner_path: item.inner_path
		}, h("span.checkbox"))

	renderItem: (item) =>
		if item.type == "parent"
			href = @url_root.replace(/^(.*)\/.{2,255}?$/, "$1/")
		else if item.type == "dir"
			href = @url_root + item.name
		else
			href = @url_root.replace(/^\/list\//, "/") + item.name

		inner_path = @inner_path + item.name
		href_edit = @getEditHref(inner_path)
		is_dir = item.type in ["dir", "parent"]
		ext = item.name.split(".").pop()

		is_editing = inner_path == Page.file_editor?.inner_path
		is_editable = not is_dir and item.size < 1024 * 1024 and ext not in BINARY_EXTENSIONS
		is_modified = @item_list.isModified(inner_path)
		is_added = @item_list.isAdded(inner_path)
		optional_info = @item_list.getOptionalInfo(inner_path)

		style = ""
		title = ""

		if optional_info
			downloaded_percent = optional_info.downloaded_percent
			if not downloaded_percent
				downloaded_percent = 0
			style += "background: linear-gradient(90deg, #fff6dd, #{downloaded_percent}%, white, #{downloaded_percent}%, white);"
			is_added = false

		if item.ignored
			is_added = false

		if is_modified then title += " (modified)"
		if is_added then title += " (new)"
		if optional_info or item.optional_empty then title += " (optional)"
		if item.ignored then title += " (ignored from content.json)"

		classes = {
			"type-#{item.type}": true, editing: is_editing, nobuttons: not is_editable, selected: @selected[inner_path],
			modified: is_modified, added: is_added, ignored: item.ignored, optional: optional_info, optional_empty: item.optional_empty
		}

		h("div.tr", {key: item.name, classes: classes, style: style, onmouseenter: @handleRowMouseenter, inner_path: inner_path}, [
			h("div.td.pre", {title: title},
				@renderItemCheckbox(item)
			),
			h("div.td.name", h("a.link", {href: href}, item.name))
			h("div.td.buttons", if is_editable then h("a.edit", {href: href_edit}, if Page.site_info.settings.own then "Edit" else "View"))
			h("div.td.size", if is_dir then "[DIR]" else Text.formatSize(item.size))
		])


	renderItems: =>
		return [
			if @item_list.error and not @item_list.items.length and not @item_list.updating then [
					h("div.tr", {key: "error"}, h("div.td.full.error", @item_list.error))
				],
			if @inner_path then @renderItem({"name": "..", type: "parent", size: 0})
			@item_list.items.map @renderItem
		]

	renderFoot: =>
		files = (item for item in @item_list.items when item.type not in ["parent", "dir"])
		dirs = (item for item in @item_list.items when item.type == "dir")
		if files.length
			total_size = (item.size for file in files).reduce (a, b) -> a + b
		else
			total_size = 0

		foot_text = "Total: "
		foot_text += "#{dirs.length} dir, #{files.length} file in #{Text.formatSize(total_size)}"

		return [
			if dirs.length or files.length or Page.site_info?.settings?.own
				h("div.tr.foot-info.foot", h("div.td.full", [
					if @item_list.updating
						"Updating file list..."
					else
						if dirs.length or files.length then foot_text
					if Page.site_info?.settings?.own
						h("div.create", [
							h("a.link", {href: "#Create+new+file", onclick: @handleNewFileClick}, "+ New")
							@menu_create.render()
						])
				]))
		]

	render: =>
		if @need_update
			@update()
			@need_update = false

			if not @item_list.items
				return []

		return h("div.files", [
			@renderSelectbar(),
			@renderHead(),
			h("div.tbody", @renderItems()),
			@renderFoot()
		])

window.FileList = FileList