class Console extends Class
	constructor: (@sidebar) ->
		@tag = null
		@opened = false
		@filter = null
		@tab_types = [
			{title: "All", filter: ""},
			{title: "Info", filter: "INFO"},
			{title: "Warning", filter: "WARNING"},
			{title: "Error", filter: "ERROR"}
		]
		@read_size = 32 * 1024
		@tab_active = ""
		#@filter = @sidebar.wrapper.site_info.address_short
		handleMessageWebsocket_original = @sidebar.wrapper.handleMessageWebsocket
		@sidebar.wrapper.handleMessageWebsocket = (message) =>
			if message.cmd == "logLineAdd" and message.params.stream_id == @stream_id
				@addLines(message.params.lines)
			else
				handleMessageWebsocket_original(message)

		$(window).on "hashchange", =>
			if window.top.location.hash.startsWith("#ZeroNet:Console")
				@open()

		if window.top.location.hash.startsWith("#ZeroNet:Console")
			setTimeout (=> @open()), 10

	createHtmltag: ->
		if not @container
			@container = $("""
			<div class="console-container">
				<div class="console">
					<div class="console-top">
						<div class="console-tabs"></div>
						<div class="console-text">Loading...</div>
					</div>
					<div class="console-middle">
						<div class="mynode"></div>
						<div class="peers">
							<div class="peer"><div class="line"></div><a href="#" class="icon">\u25BD</div></div>
						</div>
					</div>
				</div>
			</div>
			""")
			@text = @container.find(".console-text")
			@text_elem = @text[0]
			@tabs = @container.find(".console-tabs")

			@text.on "mousewheel", (e) =>  # Stop animation on manual scrolling
				if e.originalEvent.deltaY < 0
					@text.stop()
				RateLimit 300, @checkTextIsBottom

			@text.is_bottom = true

			@container.appendTo(document.body)
			@tag = @container.find(".console")
			for tab_type in @tab_types
				tab = $("<a></a>", {href: "#", "data-filter": tab_type.filter, "data-title": tab_type.title}).text(tab_type.title)
				if tab_type.filter == @tab_active
					tab.addClass("active")
				tab.on("click", @handleTabClick)
				if window.top.location.hash.endsWith(tab_type.title)
					@log "Triggering click on", tab
					tab.trigger("click")
				@tabs.append(tab)

			@container.on "mousedown touchend touchcancel", (e) =>
				if e.target != e.currentTarget
					return true
				@log "closing"
				if $(document.body).hasClass("body-console")
					@close()
					return true

			@loadConsoleText()

	checkTextIsBottom: =>
		@text.is_bottom = Math.round(@text_elem.scrollTop + @text_elem.clientHeight) >= @text_elem.scrollHeight - 15

	toColor: (text, saturation=60, lightness=70) ->
		hash = 0
		for i in [0..text.length-1]
			hash += text.charCodeAt(i)*i
			hash = hash % 1777
		return "hsl(" + (hash % 360) + ",#{saturation}%,#{lightness}%)";

	formatLine: (line) =>
		match = line.match(/(\[.*?\])[ ]+(.*?)[ ]+(.*?)[ ]+(.*)/)
		if not match
			return line.replace(/\</g, "&lt;").replace(/\>/g, "&gt;")

		[line, added, level, module, text] = line.match(/(\[.*?\])[ ]+(.*?)[ ]+(.*?)[ ]+(.*)/)
		added = "<span style='color: #dfd0fa'>#{added}</span>"
		level = "<span style='color: #{@toColor(level, 100)};'>#{level}</span>"
		module = "<span style='color: #{@toColor(module, 60)}; font-weight: bold;'>#{module}</span>"

		text = text.replace(/(Site:[A-Za-z0-9\.]+)/g, "<span style='color: #AAAAFF'>$1</span>")
		text = text.replace(/\</g, "&lt;").replace(/\>/g, "&gt;")
		#text = text.replace(/( [0-9\.]+(|s|ms))/g, "<span style='color: #FFF;'>$1</span>")
		return "#{added} #{level} #{module} #{text}"


	addLines: (lines, animate=true) =>
		html_lines = []
		@logStart "formatting"
		for line in lines
			html_lines.push @formatLine(line)
		@logEnd "formatting"
		@logStart "adding"
		@text.append(html_lines.join("<br>") + "<br>")
		@logEnd "adding"
		if @text.is_bottom and animate
			@text.stop().animate({scrollTop: @text_elem.scrollHeight - @text_elem.clientHeight + 1}, 600, 'easeInOutCubic')


	loadConsoleText: =>
		@sidebar.wrapper.ws.cmd "consoleLogRead", {filter: @filter, read_size: @read_size}, (res) =>
			@text.html("")
			pos_diff = res["pos_end"] - res["pos_start"]
			size_read = Math.round(pos_diff/1024)
			size_total = Math.round(res['pos_end']/1024)
			@text.append("<br><br>")
			@text.append("Displaying #{res.lines.length} of #{res.num_found} lines found in the last #{size_read}kB of the log file. (#{size_total}kB total)<br>")
			@addLines res.lines, false
			@text_elem.scrollTop = @text_elem.scrollHeight
		if @stream_id
			@sidebar.wrapper.ws.cmd "consoleLogStreamRemove", {stream_id: @stream_id}
		@sidebar.wrapper.ws.cmd "consoleLogStream", {filter: @filter}, (res) =>
			@stream_id = res.stream_id

	close: =>
		window.top.location.hash = ""
		@sidebar.move_lock = "y"
		@sidebar.startDrag()
		@sidebar.stopDrag()

	open: =>
		@sidebar.startDrag()
		@sidebar.moved("y")
		@sidebar.fixbutton_targety = @sidebar.page_height - @sidebar.fixbutton_inity - 50
		@sidebar.stopDrag()

	onOpened: =>
		@sidebar.onClosed()
		@log "onOpened"

	onClosed: =>
		$(document.body).removeClass("body-console")
		if @stream_id
			@sidebar.wrapper.ws.cmd "consoleLogStreamRemove", {stream_id: @stream_id}

	cleanup: =>
		if @container
			@container.remove()
			@container = null

	stopDragY: =>
		# Animate sidebar and iframe
		if @sidebar.fixbutton_targety == @sidebar.fixbutton_inity
			# Closed
			targety = 0
			@opened = false
		else
			# Opened
			targety = @sidebar.fixbutton_targety - @sidebar.fixbutton_inity
			@onOpened()
			@opened = true

		# Revent sidebar transitions
		if @tag
			@tag.css("transition", "0.5s ease-out")
			@tag.css("transform", "translateY(#{targety}px)").one transitionEnd, =>
				@tag.css("transition", "")
				if not @opened
					@cleanup()
		# Revert body transformations
		@log "stopDragY", "opened:", @opened, targety
		if not @opened
			@onClosed()

	changeFilter: (filter) =>
		@filter = filter
		if @filter == ""
			@read_size = 32 * 1024
		else
			@read_size = 5 * 1024 * 1024
		@loadConsoleText()

	handleTabClick: (e) =>
		elem = $(e.currentTarget)
		@tab_active = elem.data("filter")
		$("a", @tabs).removeClass("active")
		elem.addClass("active")
		@changeFilter(@tab_active)
		window.top.location.hash = "#ZeroNet:Console:" + elem.data("title")
		return false

window.Console = Console
