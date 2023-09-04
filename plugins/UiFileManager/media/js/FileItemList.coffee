class FileItemList extends Class
	constructor: (@inner_path) ->
		@items = []
		@updating = false
		@files_modified = {}
		@dirs_modified = {}
		@files_added = {}
		@dirs_added = {}
		@files_optional = {}
		@items_by_name = {}

	# Update item list
	update: (cb) ->
		@updating = true
		@logStart("Updating dirlist")
		Page.cmd "dirList", {inner_path: @inner_path, stats: true}, (res) =>
			if res.error
				@error = res.error
			else
				@error = null
				pattern_ignore = RegExp("^" + Page.site_info.content?.ignore)

				@items.splice(0, @items.length)  # Remove all items

				@items_by_name = {}
				for row in res
					row.type = @getFileType(row)
					row.inner_path = @inner_path + row.name
					if Page.site_info.content?.ignore and row.inner_path.match(pattern_ignore)
						row.ignored = true
					@items.push(row)
					@items_by_name[row.name] = row

				@sort()

			if Page.site_info?.settings?.own
				@updateAddedFiles()

			@updateOptionalFiles =>
				@updating = false
				cb?()
				@logEnd("Updating dirlist", @inner_path)
				Page.projector.scheduleRender()

				@updateModifiedFiles =>
					Page.projector.scheduleRender()


	updateModifiedFiles: (cb) =>
		# Add modified attribute to changed files
		Page.cmd "siteListModifiedFiles", [], (res) =>
			@files_modified = {}
			@dirs_modified = {}
			for inner_path in res.modified_files
				@files_modified[inner_path] = true
				dir_inner_path = ""
				dir_parts = inner_path.split("/")
				for dir_part in dir_parts[..-2]
					if dir_inner_path
						dir_inner_path += "/#{dir_part}"
					else
						dir_inner_path = dir_part
					@dirs_modified[dir_inner_path] = true

			cb?()

	# Update newly added items list since last sign
	updateAddedFiles: =>
		Page.cmd "fileGet", "content.json", (res) =>
			if not res
				return false

			content = JSON.parse(res)

			# Check new files
			if not content.files?
				return false

			@files_added = {}

			for file in @items
				if file.name == "content.json" or file.is_dir
					continue
				if not content.files[@inner_path + file.name]
					@files_added[@inner_path + file.name] = true

			# Check new dirs
			@dirs_added = {}

			dirs_content = {}
			for file_name of Object.assign({}, content.files, content.files_optional)
				if not file_name.startsWith(@inner_path)
					continue

				pattern = new RegExp("#{@inner_path}(.*?)/")
				match = file_name.match(pattern)

				if not match
					continue

				dirs_content[match[1]] = true

			for file in @items
				if not file.is_dir
					continue
				if not dirs_content[file.name]
					@dirs_added[@inner_path + file.name] = true

	# Update optional files list
	updateOptionalFiles: (cb) =>
		Page.cmd "optionalFileList", {filter: ""}, (res) =>
			@files_optional = {}
			for optional_file in res
				@files_optional[optional_file.inner_path] = optional_file

			@addOptionalFilesToItems()

			cb?()

	# Add optional files to item list
	addOptionalFilesToItems: =>
		is_added = false
		for inner_path, optional_file of @files_optional
			if optional_file.inner_path.startsWith(@inner_path)
				if @getDirectory(optional_file.inner_path) == @inner_path
					# Add optional file to list
					file_name = @getFileName(optional_file.inner_path)
					if not @items_by_name[file_name]
						row = {
							"name": file_name, "type": "file", "optional_empty": true,
							"size": optional_file.size, "is_dir": false, "inner_path": optional_file.inner_path
						}
						@items.push(row)
						@items_by_name[file_name] = row
						is_added = true
				else
					# Add optional dir to list
					dir_name = optional_file.inner_path.replace(@inner_path, "").match(/(.*?)\//, "")?[1]
					if dir_name and not @items_by_name[dir_name]
						row = {
							"name": dir_name, "type": "dir", "optional_empty": true,
							"size": 0, "is_dir": true, "inner_path": optional_file.inner_path
						}
						@items.push(row)
						@items_by_name[dir_name] = row
						is_added = true

		if is_added
			@sort()

	getFileType: (file) =>
		if file.is_dir
			return "dir"
		else
			return "unknown"

	getDirectory: (inner_path) ->
		if inner_path.indexOf("/") != -1
			return inner_path.replace(/^(.*\/)(.*?)$/, "$1")
		else
			return ""

	getFileName: (inner_path) ->
		return inner_path.replace(/^(.*\/)(.*?)$/, "$2")


	isModified: (inner_path) =>
		return @files_modified[inner_path] or @dirs_modified[inner_path]

	isAdded: (inner_path) =>
		return @files_added[inner_path] or @dirs_added[inner_path]

	hasPermissionDelete: (file) =>
		if file.type in ["dir", "parent"]
			return false

		if file.inner_path == "content.json"
			return false

		optional_info = @getOptionalInfo(file.inner_path)
		if optional_info and optional_info.downloaded_percent > 0
			return true
		else
			return Page.site_info?.settings?.own

	getOptionalInfo: (inner_path) =>
		return @files_optional[inner_path]

	sort: =>
		@items.sort (a, b) ->
			return (b.is_dir - a.is_dir) || a.name.localeCompare(b.name)


window.FileItemList = FileItemList