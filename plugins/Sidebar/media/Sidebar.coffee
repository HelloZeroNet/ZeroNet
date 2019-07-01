class Sidebar extends Class
	constructor: (@wrapper) ->
		@tag = null
		@container = null
		@opened = false
		@width = 410
		@console = new Console(@)
		@fixbutton = $(".fixbutton")
		@fixbutton_addx = 0
		@fixbutton_addy = 0
		@fixbutton_initx = 0
		@fixbutton_inity = 15
		@fixbutton_targetx = 0
		@move_lock = null
		@page_width = $(window).width()
		@page_height = $(window).height()
		@frame = $("#inner-iframe")
		@initFixbutton()
		@dragStarted = 0
		@globe = null
		@preload_html = null

		@original_set_site_info = @wrapper.setSiteInfo  # We going to override this, save the original

		# Start in opened state for debugging
		if false
			@startDrag()
			@moved()
			@fixbutton_targetx = @fixbutton_initx - @width
			@stopDrag()


	initFixbutton: ->

		# Detect dragging
		@fixbutton.on "mousedown touchstart", (e) =>
			if e.button > 0  # Right or middle click
				return
			e.preventDefault()

			# Disable previous listeners
			@fixbutton.off "click touchend touchcancel"

			# Make sure its not a click
			@dragStarted = (+ new Date)

			# Fullscreen drag bg to capture mouse events over iframe
			$(".drag-bg").remove()
			$("<div class='drag-bg'></div>").appendTo(document.body)

			$("body").one "mousemove touchmove", (e) =>
				mousex = e.pageX
				mousey = e.pageY
				if not mousex
					mousex = e.originalEvent.touches[0].pageX
					mousey = e.originalEvent.touches[0].pageY

				@fixbutton_addx = @fixbutton.offset().left - mousex
				@fixbutton_addy = @fixbutton.offset().top - mousey
				@startDrag()
		@fixbutton.parent().on "click touchend touchcancel", (e) =>
			if (+ new Date) - @dragStarted < 100
				window.top.location = @fixbutton.find(".fixbutton-bg").attr("href")
			@stopDrag()
		@resized()
		$(window).on "resize", @resized

	resized: =>
		@page_width = $(window).width()
		@page_height = $(window).height()
		@fixbutton_initx = @page_width - 75  # Initial x position
		if @opened
			@fixbutton.css
				left: @fixbutton_initx - @width
		else
			@fixbutton.css
				left: @fixbutton_initx

	# Start dragging the fixbutton
	startDrag: ->
		#@move_lock = "x"  # Temporary until internals not finished
		@log "startDrag", @fixbutton_initx, @fixbutton_inity
		@fixbutton_targetx = @fixbutton_initx  # Fallback x position
		@fixbutton_targety = @fixbutton_inity  # Fallback y position

		@fixbutton.addClass("dragging")

		# IE position wrap fix
		if navigator.userAgent.indexOf('MSIE') != -1 or navigator.appVersion.indexOf('Trident/') > 0
			@fixbutton.css("pointer-events", "none")

		# Don't go to homepage
		@fixbutton.one "click", (e) =>
			@stopDrag()
			@fixbutton.removeClass("dragging")
			moved_x = Math.abs(@fixbutton.offset().left - @fixbutton_initx)
			moved_y = Math.abs(@fixbutton.offset().top - @fixbutton_inity)
			if moved_x > 5 or moved_y > 10
				# If moved more than some pixel the button then don't go to homepage
				e.preventDefault()

		# Animate drag
		@fixbutton.parents().on "mousemove touchmove", @animDrag
		@fixbutton.parents().on "mousemove touchmove" ,@waitMove

		# Stop dragging listener
		@fixbutton.parents().one "mouseup touchend touchcancel", (e) =>
			e.preventDefault()
			@stopDrag()


	# Wait for moving the fixbutton
	waitMove: (e) =>
		document.body.style.perspective = "1000px"
		document.body.style.height = "100%"
		document.body.style.willChange = "perspective"
		document.documentElement.style.height = "100%"
		#$(document.body).css("backface-visibility", "hidden").css("perspective", "1000px").css("height", "900px")
		# $("iframe").css("backface-visibility", "hidden")

		moved_x = Math.abs(parseInt(@fixbutton[0].style.left) - @fixbutton_targetx)
		moved_y = Math.abs(parseInt(@fixbutton[0].style.top) - @fixbutton_targety)
		if moved_x > 5 and (+ new Date) - @dragStarted + moved_x > 50
			@moved("x")
			@fixbutton.stop().animate {"top": @fixbutton_inity}, 1000
			@fixbutton.parents().off "mousemove touchmove" ,@waitMove

		else if moved_y > 5 and (+ new Date) - @dragStarted + moved_y > 50
			@moved("y")
			@fixbutton.parents().off "mousemove touchmove" ,@waitMove

	moved: (direction) ->
		@log "Moved", direction
		@move_lock = direction
		if direction == "y"
			$(document.body).addClass("body-console")
			return @console.createHtmltag()
		@createHtmltag()
		$(document.body).addClass("body-sidebar")
		@container.on "mousedown touchend touchcancel", (e) =>
			if e.target != e.currentTarget
				return true
			@log "closing"
			if $(document.body).hasClass("body-sidebar")
				@close()
				return true

		$(window).off "resize"
		$(window).on "resize", =>
			$(document.body).css "height", $(window).height()
			@scrollable()
			@resized()

		# Override setsiteinfo to catch changes
		@wrapper.setSiteInfo = (site_info) =>
			@setSiteInfo(site_info)
			@original_set_site_info.apply(@wrapper, arguments)

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
			@wrapper.ws.cmd "sidebarGetHtmlTag", {}, @setHtmlTag

	setHtmlTag: (res) =>
		if @tag.find(".content").children().length == 0 # First update
			@log "Creating content"
			@container.addClass("loaded")
			morphdom(@tag.find(".content")[0], '<div class="content">'+res+'</div>')
			# @scrollable()
			@when_loaded.resolve()

		else  # Not first update, patch the html to keep unchanged dom elements
			morphdom @tag.find(".content")[0], '<div class="content">'+res+'</div>', {
				onBeforeMorphEl: (from_el, to_el) ->  # Ignore globe loaded state
					if from_el.className == "globe" or from_el.className.indexOf("noupdate") >= 0
						return false
					else
						return true
				}

		# Save and forgot privatekey for site signing
		@tag.find("#privatekey-add").off("click, touchend").on "click touchend", (e) =>
			@wrapper.displayPrompt "Enter your private key:", "password", "Save", "", (privatekey) =>
				@wrapper.ws.cmd "userSetSitePrivatekey", [privatekey], (res) =>
					@wrapper.notifications.add "privatekey", "done", "Private key saved for site signing", 5000
			return false

		@tag.find("#privatekey-forgot").off("click, touchend").on "click touchend", (e) =>
			@wrapper.displayConfirm "Remove saved private key for this site?", "Forgot", (res) =>
				if not res
					return false
				@wrapper.ws.cmd "userSetSitePrivatekey", [""], (res) =>
					@wrapper.notifications.add "privatekey", "done", "Saved private key removed", 5000
			return false



	animDrag: (e) =>
		mousex = e.pageX
		mousey = e.pageY
		if not mousex and e.originalEvent.touches
			mousex = e.originalEvent.touches[0].pageX
			mousey = e.originalEvent.touches[0].pageY

		overdrag = @fixbutton_initx - @width - mousex
		if overdrag > 0  # Overdragged
			overdrag_percent = 1 + overdrag/300
			mousex = (mousex + (@fixbutton_initx-@width)*overdrag_percent)/(1+overdrag_percent)
		targetx = @fixbutton_initx - mousex - @fixbutton_addx
		targety = @fixbutton_inity - mousey - @fixbutton_addy

		if @move_lock == "x"
			targety = @fixbutton_inity
		else if @move_lock == "y"
			targetx = @fixbutton_initx

		if not @move_lock or @move_lock == "x"
			@fixbutton[0].style.left = (mousex + @fixbutton_addx) + "px"
			if @tag
				@tag[0].style.transform = "translateX(#{0 - targetx}px)"

		if not @move_lock or @move_lock == "y"
			@fixbutton[0].style.top = (mousey + @fixbutton_addy) + "px"
			if @console.tag
				@console.tag[0].style.transform = "translateY(#{0 - targety}px)"

		#if @move_lock == "x"
			# @fixbutton[0].style.left = "#{@fixbutton_targetx} px"
			#@fixbutton[0].style.top = "#{@fixbutton_inity}px"
		#if @move_lock == "y"
		#	@fixbutton[0].style.top = "#{@fixbutton_targety} px"

		# Check if opened
		if (not @opened and targetx > @width/3) or (@opened and targetx > @width*0.9)
			@fixbutton_targetx = @fixbutton_initx - @width  # Make it opened
		else
			@fixbutton_targetx = @fixbutton_initx

		if (not @console.opened and 0 - targety > @page_height/10) or (@console.opened and 0 - targety > @page_height*0.8)
			@fixbutton_targety = @page_height - @fixbutton_inity - 50
		else
			@fixbutton_targety = @fixbutton_inity


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
		if @fixbutton_targetx != @fixbutton.offset().left or @fixbutton_targety != @fixbutton.offset().top
			# Animate fixbutton
			if @move_lock == "y"
				top = @fixbutton_targety
				left = @fixbutton_initx
			if @move_lock == "x"
				top = @fixbutton_inity
				left = @fixbutton_targetx
			@fixbutton.stop().animate {"left": left, "top": top}, 500, "easeOutBack", =>
				# Switch back to auto align
				if @fixbutton_targetx == @fixbutton_initx  # Closed
					@fixbutton.css("left", "auto")
				else  # Opened
					@fixbutton.css("left", left)

				$(".fixbutton-bg").trigger "mouseout"  # Switch fixbutton back to normal status

			@stopDragX()
			@console.stopDragY()
		@move_lock = null

	stopDragX: ->
		# Animate sidebar and iframe
		if @fixbutton_targetx == @fixbutton_initx or @move_lock == "y"
			# Closed
			targetx = 0
			@opened = false
		else
			# Opened
			targetx = @width
			if @opened
				@onOpened()
			else
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
					if @tag
						@tag.remove()
						@tag = null

		# Revert body transformations
		@log "stopdrag", "opened:", @opened
		if not @opened
			@onClosed()

	sign: (inner_path, privatekey) ->
		@wrapper.displayProgress("sign", "Signing: #{inner_path}...", 0)
		@wrapper.ws.cmd "siteSign", {privatekey: privatekey, inner_path: inner_path, update_changed_files: true}, (res) =>
			if res == "ok"
				@wrapper.displayProgress("sign", "#{inner_path} signed!", 100)
			else
				@wrapper.displayProgress("sign", "Error signing #{inner_path}", -1)

	publish: (inner_path, privatekey) ->
		@wrapper.ws.cmd "sitePublish", {privatekey: privatekey, inner_path: inner_path, sign: true, update_changed_files: true}, (res) =>
			if res == "ok"
				@wrapper.notifications.add "sign", "done", "#{inner_path} Signed and published!", 5000

	onOpened: ->
		@log "Opened"
		@scrollable()

		# Re-calculate height when site admin opened or closed
		@tag.find("#checkbox-owned, #checkbox-autodownloadoptional").off("click touchend").on "click touchend", =>
			setTimeout (=>
				@scrollable()
			), 300

		# Site limit button
		@tag.find("#button-sitelimit").off("click touchend").on "click touchend", =>
			@wrapper.ws.cmd "siteSetLimit", $("#input-sitelimit").val(), (res) =>
				if res == "ok"
					@wrapper.notifications.add "done-sitelimit", "done", "Site storage limit modified!", 5000
				@updateHtmlTag()
			return false

		# Site autodownload limit button
		@tag.find("#button-autodownload_bigfile_size_limit").off("click touchend").on "click touchend", =>
			@wrapper.ws.cmd "siteSetAutodownloadBigfileLimit", $("#input-autodownload_bigfile_size_limit").val(), (res) =>
				if res == "ok"
					@wrapper.notifications.add "done-bigfilelimit", "done", "Site bigfile auto download limit modified!", 5000
				@updateHtmlTag()
			return false

		# Database reload
		@tag.find("#button-dbreload").off("click touchend").on "click touchend", =>
			@wrapper.ws.cmd "dbReload", [], =>
				@wrapper.notifications.add "done-dbreload", "done", "Database schema reloaded!", 5000
				@updateHtmlTag()
			return false

		# Database rebuild
		@tag.find("#button-dbrebuild").off("click touchend").on "click touchend", =>
			@wrapper.notifications.add "done-dbrebuild", "info", "Database rebuilding...."
			@wrapper.ws.cmd "dbRebuild", [], =>
				@wrapper.notifications.add "done-dbrebuild", "done", "Database rebuilt!", 5000
				@updateHtmlTag()
			return false

		# Update site
		@tag.find("#button-update").off("click touchend").on "click touchend", =>
			@tag.find("#button-update").addClass("loading")
			@wrapper.ws.cmd "siteUpdate", @wrapper.site_info.address, =>
				@wrapper.notifications.add "done-updated", "done", "Site updated!", 5000
				@tag.find("#button-update").removeClass("loading")
			return false

		# Pause site
		@tag.find("#button-pause").off("click touchend").on "click touchend", =>
			@tag.find("#button-pause").addClass("hidden")
			@wrapper.ws.cmd "sitePause", @wrapper.site_info.address
			return false

		# Resume site
		@tag.find("#button-resume").off("click touchend").on "click touchend", =>
			@tag.find("#button-resume").addClass("hidden")
			@wrapper.ws.cmd "siteResume", @wrapper.site_info.address
			return false

		# Delete site
		@tag.find("#button-delete").off("click touchend").on "click touchend", =>
			@wrapper.displayConfirm "Are you sure?", ["Delete this site", "Blacklist"], (confirmed) =>
				if confirmed == 1
					@tag.find("#button-delete").addClass("loading")
					@wrapper.ws.cmd "siteDelete", @wrapper.site_info.address, ->
						document.location = $(".fixbutton-bg").attr("href")
				else if confirmed == 2
					@wrapper.displayPrompt "Blacklist this site", "text", "Delete and Blacklist", "Reason", (reason) =>
						@tag.find("#button-delete").addClass("loading")
						@wrapper.ws.cmd "siteblockAdd", [@wrapper.site_info.address, reason]
						@wrapper.ws.cmd "siteDelete", @wrapper.site_info.address, ->
							document.location = $(".fixbutton-bg").attr("href")


			return false

		# Owned checkbox
		@tag.find("#checkbox-owned").off("click touchend").on "click touchend", =>
			@wrapper.ws.cmd "siteSetOwned", [@tag.find("#checkbox-owned").is(":checked")]

		# Owned checkbox
		@tag.find("#checkbox-autodownloadoptional").off("click touchend").on "click touchend", =>
			@wrapper.ws.cmd "siteSetAutodownloadoptional", [@tag.find("#checkbox-autodownloadoptional").is(":checked")]

		# Change identity button
		@tag.find("#button-identity").off("click touchend").on "click touchend", =>
			@wrapper.ws.cmd "certSelect"
			return false

		# Save settings
		@tag.find("#button-settings").off("click touchend").on "click touchend", =>
			@wrapper.ws.cmd "fileGet", "content.json", (res) =>
				data = JSON.parse(res)
				data["title"] = $("#settings-title").val()
				data["description"] = $("#settings-description").val()
				json_raw = unescape(encodeURIComponent(JSON.stringify(data, undefined, '\t')))
				@wrapper.ws.cmd "fileWrite", ["content.json", btoa(json_raw), true], (res) =>
					if res != "ok" # fileWrite failed
						@wrapper.notifications.add "file-write", "error", "File write error: #{res}"
					else
						@wrapper.notifications.add "file-write", "done", "Site settings saved!", 5000
						if @wrapper.site_info.privatekey
							@wrapper.ws.cmd "siteSign", {privatekey: "stored", inner_path: "content.json", update_changed_files: true}
						@updateHtmlTag()
			return false


		# Open site directory
		@tag.find("#link-directory").off("click touchend").on "click touchend", =>
			@wrapper.ws.cmd "serverShowdirectory", ["site", @wrapper.site_info.address]
			return false

		# Copy site with peers
		@tag.find("#link-copypeers").off("click touchend").on "click touchend", (e) =>
			copy_text = e.currentTarget.href
			handler = (e) =>
				e.clipboardData.setData('text/plain', copy_text)
				e.preventDefault()
				@wrapper.notifications.add "copy", "done", "Site address with peers copied to your clipboard", 5000
				document.removeEventListener('copy', handler, true)

			document.addEventListener('copy', handler, true)
			document.execCommand('copy')
			return false

		# Sign and publish content.json
		$(document).on "click touchend", =>
			@tag?.find("#button-sign-publish-menu").removeClass("visible")
			@tag?.find(".contents + .flex").removeClass("sign-publish-flex")

		@tag.find(".contents-content").off("click touchend").on "click touchend", (e) =>
			$("#input-contents").val(e.currentTarget.innerText);
			return false;

		menu = new Menu(@tag.find("#menu-sign-publish"))
		menu.elem.css("margin-top", "-130px")  # Open upwards
		menu.addItem "Sign", =>
			inner_path = @tag.find("#input-contents").val()

			@wrapper.ws.cmd "fileRules", {inner_path: inner_path}, (rules) =>
				if @wrapper.site_info.auth_address in rules.signers
					# ZeroID or other ID provider
					@sign(inner_path)
				else if @wrapper.site_info.privatekey
					# Privatekey stored in users.json
					@sign(inner_path, "stored")
				else
					# Ask the user for privatekey
					@wrapper.displayPrompt "Enter your private key:", "password", "Sign", "", (privatekey) => # Prompt the private key
						@sign(inner_path, privatekey)

			@tag.find(".contents + .flex").removeClass "active"
			menu.hide()

		menu.addItem "Publish", =>
			inner_path = @tag.find("#input-contents").val()
			@wrapper.ws.cmd "sitePublish", {"inner_path": inner_path, "sign": false}

			@tag.find(".contents + .flex").removeClass "active"
			menu.hide()

		@tag.find("#menu-sign-publish").off("click touchend").on "click touchend", =>
			if window.visible_menu == menu
				@tag.find(".contents + .flex").removeClass "active"
				menu.hide()
			else
				@tag.find(".contents + .flex").addClass "active"
				@tag.find(".content-wrapper").prop "scrollTop", 10000
				menu.show()
			return false

		$("body").on "click", =>
			if @tag
				@tag.find(".contents + .flex").removeClass "active"

		@tag.find("#button-sign-publish").off("click touchend").on "click touchend", =>
			inner_path = @tag.find("#input-contents").val()

			@wrapper.ws.cmd "fileRules", {inner_path: inner_path}, (rules) =>
				if @wrapper.site_info.auth_address in rules.signers
					# ZeroID or other ID provider
					@publish(inner_path, null)
				else if @wrapper.site_info.privatekey
					# Privatekey stored in users.json
					@publish(inner_path, "stored")
				else
					# Ask the user for privatekey
					@wrapper.displayPrompt "Enter your private key:", "password", "Sign", "", (privatekey) => # Prompt the private key
						@publish(inner_path, privatekey)
			return false

		# Close
		@tag.find(".close").off("click touchend").on "click touchend", (e) =>
			@close()
			return false

		@loadGlobe()

	close: ->
		@move_lock = "x"
		@startDrag()
		@stopDrag()


	onClosed: ->
		$(window).off "resize"
		$(window).on "resize", @resized
		$(document.body).css("transition", "0.6s ease-in-out").removeClass("body-sidebar").on transitionEnd, (e) =>
			if e.target == document.body and not $(document.body).hasClass("body-sidebar") and not $(document.body).hasClass("body-console")
				$(document.body).css("height", "auto").css("perspective", "").css("will-change", "").css("transition", "").off transitionEnd
				@unloadGlobe()

		# We dont need site info anymore
		@wrapper.setSiteInfo = @original_set_site_info


	loadGlobe: =>
		if @tag.find(".globe").hasClass("loading")
			setTimeout (=>
				if typeof(DAT) == "undefined"  # Globe script not loaded, do it first
					script_tag = $("<script>")
					script_tag.attr("nonce", @wrapper.script_nonce)
					script_tag.attr("src", "/uimedia/globe/all.js")
					script_tag.on("load", @displayGlobe)
					document.head.appendChild(script_tag[0])
				else
					@displayGlobe()
			), 600


	displayGlobe: =>
		img = new Image();
		img.src = "/uimedia/globe/world.jpg";
		img.onload = =>
			@wrapper.ws.cmd "sidebarGetPeers", [], (globe_data) =>
				if @globe
					@globe.scene.remove(@globe.points)
					@globe.addData( globe_data, {format: 'magnitude', name: "hello", animated: false} )
					@globe.createPoints()
					@tag?.find(".globe").removeClass("loading")
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


wrapper = window.wrapper
setTimeout ( ->
	window.sidebar = new Sidebar(wrapper)
), 500


window.transitionEnd = 'transitionend webkitTransitionEnd oTransitionEnd otransitionend'
