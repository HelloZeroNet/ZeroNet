class Console extends Class
	constructor: (@sidebar) ->
		@tag = null
		@opened = false
		@filter = null
		#@filter = @sidebar.wrapper.site_info.address_short
		handleMessageWebsocket_original = @sidebar.wrapper.handleMessageWebsocket
		@sidebar.wrapper.handleMessageWebsocket = (message) =>
			if message.cmd == "logLineAdd" and message.params.stream_id == @stream_id
				@addLines(message.params.lines)
			else
				handleMessageWebsocket_original(message)

		if window.top.location.hash == "#console"
			setTimeout (=> @open()), 10

	createHtmltag: ->
		if not @container
			@container = $("""
			<div class="console-container">
				<div class="console">
					<div class="console-top">
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

			@text.on "mousewheel", (e) =>  # Stop animation on manual scrolling
				if e.originalEvent.deltaY < 0
					@text.stop()
				RateLimit 300, @checkTextIsBottom

			@text.is_bottom = true

			@container.appendTo(document.body)
			@tag = @container.find(".console")

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
		@sidebar.wrapper.ws.cmd "consoleLogRead", {filter: @filter}, (res) =>
			@text.html("")
			pos_diff = res["pos_end"] - res["pos_start"]
			size_read = Math.round(pos_diff/1024)
			size_total = Math.round(res['pos_end']/1024)
			@text.append("Displaying #{res.lines.length} of #{res.num_found} lines found in the last #{size_read}kB of the log file. (#{size_total}kB total)<br>")
			@addLines res.lines, false
			@text_elem.scrollTop = @text_elem.scrollHeight
		@sidebar.wrapper.ws.cmd "consoleLogStream", {filter: @filter}, (res) =>
			@stream_id = res.stream_id

	close: =>
		@sidebar.move_lock = "y"
		@sidebar.startDrag()
		@sidebar.stopDrag()

	open: =>
		@createHtmltag()
		@sidebar.fixbutton_targety = @sidebar.page_height
		@stopDragY()

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

window.Console = Console