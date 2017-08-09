class Sidebar extends Class
	constructor: ->
		@tag = null
		@container = null
		@opened = false
		@width = 410
		@fixbutton = $(".fixbutton")
		@fixbutton_addx = 0
		@fixbutton_initx = 0
		@fixbutton_targetx = 0
		@page_width = $(window).width()
		@frame = $("#inner-iframe")
		@initFixbutton()
		@dragStarted = 0
		@globe = null
		@preload_html = null

		@original_set_site_info = wrapper.setSiteInfo  # We going to override this, save the original

		# Start in opened state for debugging
		if false
			@startDrag()
			@moved()
			@fixbutton_targetx = @fixbutton_initx - @width
			@stopDrag()


	initFixbutton: ->
		###
		@fixbutton.on "mousedown touchstart", (e) =>
			if not @opened
				@logStart("Preloading")
				wrapper.ws.cmd "sidebarGetHtmlTag", {}, (res) =>
					@logEnd("Preloading")
					@preload_html = res
		###

		# Detect dragging
		@fixbutton.on "mousedown touchstart", (e) =>
			if e.button > 0  # Right or middle click
				return
			e.preventDefault()

			# Disable previous listeners
			@fixbutton.off "click touchend touchcancel"
			@fixbutton.off "mousemove touchmove"

			# Make sure its not a click
			@dragStarted = (+ new Date)
			@fixbutton.one "mousemove touchmove", (e) =>
				mousex = e.pageX
				if not mousex
					mousex = e.originalEvent.touches[0].pageX

				@fixbutton_addx = @fixbutton.offset().left-mousex
				@startDrag()
		@fixbutton.parent().on "click touchend touchcancel", (e) =>
			if (+ new Date)-@dragStarted < 100
				window.top.location = @fixbutton.find(".fixbutton-bg").attr("href")
			@stopDrag()
		@resized()
		$(window).on "resize", @resized

	resized: =>
		@page_width = $(window).width()
		@fixbutton_initx = @page_width - 75  # Initial x position
		if @opened
			@fixbutton.css
				left: @fixbutton_initx - @width
		else
			@fixbutton.css
				left: @fixbutton_initx

	# Start dragging the fixbutton
	startDrag: ->
		@log "startDrag"
		@fixbutton_targetx = @fixbutton_initx  # Fallback x position

		@fixbutton.addClass("dragging")

		# Fullscreen drag bg to capture mouse events over iframe
		$("<div class='drag-bg'></div>").appendTo(document.body)

		# IE position wrap fix
		if navigator.userAgent.indexOf('MSIE') != -1 or navigator.appVersion.indexOf('Trident/') > 0
			@fixbutton.css("pointer-events", "none")

		# Don't go to homepage
		@fixbutton.one "click", (e) =>
			@stopDrag()
			@fixbutton.removeClass("dragging")
			if Math.abs(@fixbutton.offset().left - @fixbutton_initx) > 5
				# If moved more than some pixel the button then don't go to homepage
				e.preventDefault()

		# Animate drag
		@fixbutton.parents().on "mousemove touchmove", @animDrag
		@fixbutton.parents().on "mousemove touchmove" ,@waitMove

		# Stop dragging listener
		@fixbutton.parents().on "mouseup touchend touchend touchcancel", (e) =>
			e.preventDefault()
			@stopDrag()


	# Wait for moving the fixbutton
	waitMove: (e) =>
		if Math.abs(@fixbutton.offset().left - @fixbutton_targetx) > 10 and (+ new Date)-@dragStarted > 100
			@moved()
			@fixbutton.parents().off "mousemove touchmove" ,@waitMove

	moved: ->
		@log "Moved"
		@createHtmltag()
		$(document.body).css("perspective", "1000px").addClass("body-sidebar")
		$(window).off "resize"
		$(window).on "resize", =>
			$(document.body).css "height", $(window).height()
			@scrollable()
			@resized()
		$(window).trigger "resize"

		# Override setsiteinfo to catch changes
		wrapper.setSiteInfo = (site_info) =>
			@setSiteInfo(site_info)
			@original_set_site_info.apply(wrapper, arguments)

		# Preload world.jpg
		img = new Image();
		img.src = "/uimedia/globe/world.jpg";

	setSiteInfo: (site_info) ->
		RateLimit 1500, =>
			@updateHtmlTag()
		RateLimit 30000, =>
			@displayGlobe()

	# Create the sidebar html tag
	createHtmltag: ->
		@when_loaded = $.Deferred()
		if not @container
			@container = $("""
			<div class="sidebar-container"><div class="sidebar scrollable"><div class="content-wrapper"><div class="content">
			</div></div></div></div>
			""")
			@container.appendTo(document.body)
			@tag = @container.find(".sidebar")
			@updateHtmlTag()
			@scrollable = window.initScrollable()


	updateHtmlTag: ->
		if @preload_html
			@setHtmlTag(@preload_html)
			@preload_html = null
		else
			wrapper.ws.cmd "sidebarGetHtmlTag", {}, @setHtmlTag

	setHtmlTag: (res) =>
		if @tag.find(".content").children().length == 0 # First update
			@log "Creating content"
			@container.addClass("loaded")
			morphdom(@tag.find(".content")[0], '<div class="content">'+res+'</div>')
			# @scrollable()
			@when_loaded.resolve()

		else  # Not first update, patch the html to keep unchanged dom elements
			@log "Patching content"
			morphdom @tag.find(".content")[0], '<div class="content">'+res+'</div>', {
				onBeforeMorphEl: (from_el, to_el) ->  # Ignore globe loaded state
					if from_el.className == "globe" or from_el.className.indexOf("noupdate") >= 0
						return false
					else
						return true
				}


	animDrag: (e) =>
		mousex = e.pageX
		if not mousex
			mousex = e.originalEvent.touches[0].pageX

		overdrag = @fixbutton_initx-@width-mousex
		if overdrag > 0  # Overdragged
			overdrag_percent = 1+overdrag/300
			mousex = (mousex + (@fixbutton_initx-@width)*overdrag_percent)/(1+overdrag_percent)
		targetx = @fixbutton_initx-mousex-@fixbutton_addx

		@fixbutton[0].style.left = (mousex+@fixbutton_addx)+"px"

		if @tag
			@tag[0].style.transform = "translateX(#{0-targetx}px)"

		# Check if opened
		if (not @opened and targetx > @width/3) or (@opened and targetx > @width*0.9)
			@fixbutton_targetx = @fixbutton_initx - @width  # Make it opened
		else
			@fixbutton_targetx = @fixbutton_initx


	# Stop dragging the fixbutton
	stopDrag: ->
		@fixbutton.parents().off "mousemove touchmove"
		@fixbutton.off "mousemove touchmove"
		@fixbutton.css("pointer-events", "")
		$(".drag-bg").remove()
		if not @fixbutton.hasClass("dragging")
			return
		@fixbutton.removeClass("dragging")

		# Move back to initial position
		if @fixbutton_targetx != @fixbutton.offset().left
			# Animate fixbutton
			@fixbutton.stop().animate {"left": @fixbutton_targetx}, 500, "easeOutBack", =>
				# Switch back to auto align
				if @fixbutton_targetx == @fixbutton_initx  # Closed
					@fixbutton.css("left", "auto")
				else  # Opened
					@fixbutton.css("left", @fixbutton_targetx)

				$(".fixbutton-bg").trigger "mouseout"  # Switch fixbutton back to normal status

			# Animate sidebar and iframe
			if @fixbutton_targetx == @fixbutton_initx
				# Closed
				targetx = 0
				@opened = false
			else
				# Opened
				targetx = @width
				if not @opened
					@when_loaded.done =>
						@onOpened()
				@opened = true

			# Revent sidebar transitions
			if @tag
				@tag.css("transition", "0.4s ease-out")
				@tag.css("transform", "translateX(-#{targetx}px)").one transitionEnd, =>
					@tag.css("transition", "")
					if not @opened
						@container.remove()
						@container = null
						@tag.remove()
						@tag = null

			# Revert body transformations
			@log "stopdrag", "opened:", @opened
			if not @opened
				@onClosed()


	onOpened: ->
		@log "Opened"
		@scrollable()

		# Re-calculate height when site admin opened or closed
		@tag.find("#checkbox-owned").off("click touchend").on "click touchend", =>
			setTimeout (=>
				@scrollable()
			), 300

		# Site limit button
		@tag.find("#button-sitelimit").off("click touchend").on "click touchend", =>
			wrapper.ws.cmd "siteSetLimit", $("#input-sitelimit").val(), (res) =>
				if res == "ok"
					wrapper.notifications.add "done-sitelimit", "done", "Site storage limit modified!", 5000
				@updateHtmlTag()
			return false

		# Database reload
		@tag.find("#button-dbreload").off("click touchend").on "click touchend", =>
			wrapper.ws.cmd "dbReload", [], =>
				wrapper.notifications.add "done-dbreload", "done", "Database schema reloaded!", 5000
				@updateHtmlTag()
			return false

		# Database rebuild
		@tag.find("#button-dbrebuild").off("click touchend").on "click touchend", =>
			wrapper.notifications.add "done-dbrebuild", "info", "Database rebuilding...."
			wrapper.ws.cmd "dbRebuild", [], =>
				wrapper.notifications.add "done-dbrebuild", "done", "Database rebuilt!", 5000
				@updateHtmlTag()
			return false

		# Update site
		@tag.find("#button-update").off("click touchend").on "click touchend", =>
			@tag.find("#button-update").addClass("loading")
			wrapper.ws.cmd "siteUpdate", wrapper.site_info.address, =>
				wrapper.notifications.add "done-updated", "done", "Site updated!", 5000
				@tag.find("#button-update").removeClass("loading")
			return false

		# Pause site
		@tag.find("#button-pause").off("click touchend").on "click touchend", =>
			@tag.find("#button-pause").addClass("hidden")
			wrapper.ws.cmd "sitePause", wrapper.site_info.address
			return false

		# Resume site
		@tag.find("#button-resume").off("click touchend").on "click touchend", =>
			@tag.find("#button-resume").addClass("hidden")
			wrapper.ws.cmd "siteResume", wrapper.site_info.address
			return false

		# Delete site
		@tag.find("#button-delete").off("click touchend").on "click touchend", =>
			wrapper.displayConfirm "Are you sure?", ["Delete this site", "Blacklist"], (confirmed) =>
				if confirmed == 1
					@tag.find("#button-delete").addClass("loading")
					wrapper.ws.cmd "siteDelete", wrapper.site_info.address, ->
						document.location = $(".fixbutton-bg").attr("href")
				else if confirmed == 2
					wrapper.displayPrompt "Blacklist this site", "text", "Delete and Blacklist", "Reason", (reason) =>
						@tag.find("#button-delete").addClass("loading")
						wrapper.ws.cmd "blacklistAdd", [wrapper.site_info.address, reason]
						wrapper.ws.cmd "siteDelete", wrapper.site_info.address, ->
							document.location = $(".fixbutton-bg").attr("href")


			return false

		# Owned checkbox
		@tag.find("#checkbox-owned").off("click touchend").on "click touchend", =>
			wrapper.ws.cmd "siteSetOwned", [@tag.find("#checkbox-owned").is(":checked")]

		# Owned checkbox
		@tag.find("#checkbox-autodownloadoptional").off("click touchend").on "click touchend", =>
			wrapper.ws.cmd "siteSetAutodownloadoptional", [@tag.find("#checkbox-autodownloadoptional").is(":checked")]

		# Change identity button
		@tag.find("#button-identity").off("click touchend").on "click touchend", =>
			wrapper.ws.cmd "certSelect"
			return false

		# Owned checkbox
		@tag.find("#checkbox-owned").off("click touchend").on "click touchend", =>
			wrapper.ws.cmd "siteSetOwned", [@tag.find("#checkbox-owned").is(":checked")]

		# Save settings
		@tag.find("#button-settings").off("click touchend").on "click touchend", =>
			wrapper.ws.cmd "fileGet", "content.json", (res) =>
				data = JSON.parse(res)
				data["title"] = $("#settings-title").val()
				data["description"] = $("#settings-description").val()
				json_raw = unescape(encodeURIComponent(JSON.stringify(data, undefined, '\t')))
				wrapper.ws.cmd "fileWrite", ["content.json", btoa(json_raw), true], (res) =>
					if res != "ok" # fileWrite failed
						wrapper.notifications.add "file-write", "error", "File write error: #{res}"
					else
						wrapper.notifications.add "file-write", "done", "Site settings saved!", 5000
						if wrapper.site_info.privatekey
							wrapper.ws.cmd "siteSign", {privatekey: "stored", inner_path: "content.json", update_changed_files: true}
						@updateHtmlTag()
			return false

		# Sign content.json
		@tag.find("#button-sign").off("click touchend").on "click touchend", =>
			inner_path = @tag.find("#input-contents").val()

			wrapper.ws.cmd "fileRules", {inner_path: inner_path}, (res) =>
				if wrapper.site_info.privatekey or wrapper.site_info.auth_address in res.signers
					# Privatekey stored in users.json
					wrapper.ws.cmd "siteSign", {privatekey: "stored", inner_path: inner_path, update_changed_files: true}, (res) =>
						if res == "ok"
							wrapper.notifications.add "sign", "done", "#{inner_path} Signed!", 5000

				else
					# Ask the user for privatekey
					wrapper.displayPrompt "Enter your private key:", "password", "Sign", "", (privatekey) => # Prompt the private key
						wrapper.ws.cmd "siteSign", {privatekey: privatekey, inner_path: inner_path, update_changed_files: true}, (res) =>
							if res == "ok"
								wrapper.notifications.add "sign", "done", "#{inner_path} Signed!", 5000

			return false

		# Publish content.json
		@tag.find("#button-publish").off("click touchend").on "click touchend", =>
			inner_path = @tag.find("#input-contents").val()
			@tag.find("#button-publish").addClass "loading"
			wrapper.ws.cmd "sitePublish", {"inner_path": inner_path, "sign": false}, =>
				@tag.find("#button-publish").removeClass "loading"

		# Close
		@tag.find(".close").off("click touchend").on "click touchend", (e) =>
			@startDrag()
			@stopDrag()
			return false

		@loadGlobe()


	onClosed: ->
		$(window).off "resize"
		$(window).on "resize", @resized
		$(document.body).css("transition", "0.6s ease-in-out").removeClass("body-sidebar").on transitionEnd, (e) =>
			if e.target == document.body
				$(document.body).css("height", "auto").css("perspective", "").css("transition", "").off transitionEnd
				@unloadGlobe()

		# We dont need site info anymore
		wrapper.setSiteInfo = @original_set_site_info


	loadGlobe: =>
		console.log "loadGlobe", @tag.find(".globe").hasClass("loading")
		if @tag.find(".globe").hasClass("loading")
			setTimeout (=>
				if typeof(DAT) == "undefined"  # Globe script not loaded, do it first
					$.getScript("/uimedia/globe/all.js", @displayGlobe)
				else
					@displayGlobe()
			), 600


	displayGlobe: =>
		img = new Image();
		img.src = "/uimedia/globe/world.jpg";
		img.onload = =>
			wrapper.ws.cmd "sidebarGetPeers", [], (globe_data) =>
				if @globe
					@globe.scene.remove(@globe.points)
					@globe.addData( globe_data, {format: 'magnitude', name: "hello", animated: false} )
					@globe.createPoints()
				else if typeof(DAT) != "undefined"
					try
						@globe = new DAT.Globe( @tag.find(".globe")[0], {"imgDir": "/uimedia/globe/"} )
						@globe.addData( globe_data, {format: 'magnitude', name: "hello"} )
						@globe.createPoints()
						@globe.animate()
					catch e
						console.log "WebGL error", e
						@tag?.find(".globe").addClass("error").text("WebGL not supported")

				@tag?.find(".globe").removeClass("loading")


	unloadGlobe: =>
		if not @globe
			return false
		@globe.unload()
		@globe = null


setTimeout ( ->
	window.sidebar = new Sidebar()
), 500
window.transitionEnd = 'transitionend webkitTransitionEnd oTransitionEnd otransitionend'
