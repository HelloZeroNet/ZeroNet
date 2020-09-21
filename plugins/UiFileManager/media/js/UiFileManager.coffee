window.h = maquette.h

class UiFileManager extends ZeroFrame
	init: ->
		@url_params = new URLSearchParams(window.location.search)
		@list_site = @url_params.get("site")
		@list_address = @url_params.get("address")
		@list_inner_path = @url_params.get("inner_path")
		@editor_inner_path = @url_params.get("file")
		@file_list = new FileList(@list_site, @list_inner_path)

		@site_info = null
		@server_info = null

		@is_sidebar_closed = false

		if @editor_inner_path
			@file_editor = new FileEditor(@editor_inner_path)

		window.onbeforeunload = =>
			if @file_editor?.isModified()
				return true
			else
				return null

		window.onresize = =>
			@checkBodyWidth()

		@checkBodyWidth()

		@cmd("wrapperSetViewport", "width=device-width, initial-scale=0.8")

		@cmd "serverInfo", {}, (server_info) =>
			@server_info = server_info
		@cmd "siteInfo", {}, (site_info) =>
			@cmd("wrapperSetTitle", "List: /#{@list_inner_path} - #{site_info.content.title} - ZeroNet")
			@site_info = site_info
			if @file_editor then @file_editor.on_loaded.then =>
				@file_editor.cm.setOption("readOnly", not site_info.settings.own)
				@file_editor.mode = if site_info.settings.own then "Edit" else "View"
			@projector.scheduleRender()

	checkBodyWidth: =>
		if not @file_editor
			return false

		if document.body.offsetWidth < 960 and not @is_sidebar_closed
			@is_sidebar_closed = true
			@projector?.scheduleRender()
		else if document.body.offsetWidth > 960 and @is_sidebar_closed
			@is_sidebar_closed = false
			@projector?.scheduleRender()

	onRequest: (cmd, message) =>
		if cmd == "setSiteInfo"
			@site_info = message
			RateLimitCb 1000, (cb_done) =>
				@file_list.update(cb_done)
			@projector.scheduleRender()
		else if cmd == "setServerInfo"
			@server_info = message
			@projector.scheduleRender()
		else
			@log "Unknown incoming message:", cmd

	createProjector: =>
		@projector = maquette.createProjector()
		@projector.replace($("#content"), @render)

	render: =>
		return h("div.content#content", [
			h("div.manager", {classes: {editing: @file_editor, sidebar_closed: @is_sidebar_closed}}, [
				@file_list.render(),
				if @file_editor then @file_editor.render()
			])
		])

window.Page = new UiFileManager()
window.Page.createProjector()
