class FileEditor extends Class
	constructor: (@inner_path) ->
		@need_update = true
		@on_loaded = new Promise()
		@is_loading = false
		@content = ""
		@node_cm = null
		@cm = null
		@error = null
		@is_loaded = false
		@is_modified = false
		@is_saving = false
		@mode = "Loading"

	update: ->
		is_required = Page.url_params.get("edit_mode") != "new"

		Page.cmd "fileGet", {inner_path: @inner_path, required: is_required}, (res) =>
			if res?.error
				@error = res.error
				@content = res.error
				@log "Error loading: #{@error}"
			else
				if res
					@content = res
				else
					@content = ""
					@mode = "Create"
			if not @content
				@cm.getDoc().clearHistory()
			@cm.setValue(@content)
			if not @error
				@is_loaded = true
			Page.projector.scheduleRender()

	isModified: =>
		return @content != @cm.getValue()

	storeCmNode: (node) =>
		@node_cm = node

	getMode: (inner_path) ->
		ext = inner_path.split(".").pop()
		types = {
			"py": "python",
			"json": "application/json",
			"js": "javascript",
			"coffee": "coffeescript",
			"html": "htmlmixed",
			"htm": "htmlmixed",
			"php": "htmlmixed",
			"rs": "rust",
			"css": "css",
			"md": "markdown",
			"xml": "xml",
			"svg": "xml"
		}
		return types[ext]

	foldJson: (from, to) =>
		@log "foldJson", from, to
		# Get open / close token
		startToken = '{'
		endToken = '}'
		prevLine = @cm.getLine(from.line)
		if prevLine.lastIndexOf('[') > prevLine.lastIndexOf('{')
		  startToken = '['
		  endToken = ']'

		# Get json content
		internal = @cm.getRange(from, to)
		toParse = startToken + internal + endToken

		#Get key count
		try
			parsed = JSON.parse(toParse)
			count = Object.keys(parsed).length
		catch e
			null

		return if count then "\u21A4#{count}\u21A6" else "\u2194"

	createCodeMirror: ->
		mode = @getMode(@inner_path)
		@log "Creating CodeMirror", @inner_path, mode
		options = {
			value: "Loading...",
			mode: mode,
			lineNumbers: true,
			styleActiveLine: true,
			matchBrackets: true,
			keyMap: "sublime",
			theme: "mdn-like",
			extraKeys: {"Ctrl-Space": "autocomplete"},
			foldGutter: true,
			gutters: ["CodeMirror-linenumbers", "CodeMirror-foldgutter"]

		}
		if mode == "application/json"
			options.gutters.unshift("CodeMirror-lint-markers")
			options.lint = true
			options.foldOptions = { widget: @foldJson }

		@cm = CodeMirror(@node_cm, options)
		@cm.on "changes", (changes) =>
			if @is_loaded and not @is_modified
				@is_modified = true
				Page.projector.scheduleRender()


	loadEditor: ->
		if not @is_loading
			document.getElementsByTagName("head")[0].insertAdjacentHTML(
				"beforeend",
				"""<link rel="stylesheet" href="codemirror/all.css" />"""
			)
			script = document.createElement('script')
			script.src = "codemirror/all.js"
			script.onload = =>
				@createCodeMirror()
				@on_loaded.resolve()
			document.head.appendChild(script)
		return @on_loaded

	handleSidebarButtonClick: =>
		Page.is_sidebar_closed = not Page.is_sidebar_closed
		return false

	handleSaveClick: =>
		@is_saving = true
		Page.cmd "fileWrite", [@inner_path, Text.fileEncode(@cm.getValue())], (res) =>
			@is_saving = false
			if res.error
				Page.cmd "wrapperNotification", ["error", "Error saving #{res.error}"]
			else
				@is_save_done = true
				setTimeout (() =>
					@is_save_done = false
					Page.projector.scheduleRender()
				), 2000
				@content = @cm.getValue()
				@is_modified = false
				if @mode == "Create"
					@mode = "Edit"
				Page.file_list.need_update = true
			Page.projector.scheduleRender()
		return false

	render: ->
		if @need_update
			@loadEditor().then =>
				@update()
			@need_update = false
		h("div.editor", {afterCreate: @storeCmNode, classes: {error: @error, loaded: @is_loaded}}, [
			h("a.sidebar-button", {href: "#Sidebar", onclick: @handleSidebarButtonClick}, h("span", "\u2039")),
			h("div.editor-head", [
				if @mode in ["Edit", "Create"]
					h("a.save.button",
						{href: "#Save", classes: {loading: @is_saving, done: @is_save_done, disabled: not @is_modified}, onclick: @handleSaveClick},
						if @is_save_done then "Save: done!" else "Save"
					)
				h("span.title", @mode, ": ", @inner_path)
			]),
			if @error
				h("div.error-message",
					h("h2", "Unable to load the file: #{@error}")
					h("a", {href: Page.file_list.getHref(@inner_path)}, "View in browser")
				)
		])

window.FileEditor = FileEditor