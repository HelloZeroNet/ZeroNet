class Wrapper
	constructor: (ws_url) ->
		@log "Created!"

		@loading = new Loading(@)
		@notifications = new Notifications($(".notifications"))
		@infopanel = new Infopanel($(".infopanel"))
		@infopanel.onClosed = =>
			@ws.cmd("siteSetSettingsValue", ["modified_files_notification", false])
		@infopanel.onOpened = =>
			@ws.cmd("siteSetSettingsValue", ["modified_files_notification", true])
		@fixbutton = new Fixbutton()

		window.addEventListener("message", @onMessageInner, false)
		@inner = document.getElementById("inner-iframe").contentWindow
		@ws = new ZeroWebsocket(ws_url)
		@ws.next_message_id = 1000000 # Avoid messageid collision :)
		@ws.onOpen = @onOpenWebsocket
		@ws.onClose = @onCloseWebsocket
		@ws.onMessage = @onMessageWebsocket
		@ws.connect()
		@ws_error = null # Ws error message

		@next_cmd_message_id = -1

		@site_info = null # Hold latest site info
		@server_info = null # Hold latest server info
		@event_site_info =  $.Deferred() # Event when site_info received
		@inner_loaded = false # If iframe loaded or not
		@inner_ready = false # Inner frame ready to receive messages
		@wrapperWsInited = false # Wrapper notified on websocket open
		@site_error = null # Latest failed file download
		@address = null
		@opener_tested = false
		@announcer_line = null
		@web_notifications = {}

		@allowed_event_constructors = [window.MouseEvent, window.KeyboardEvent, window.PointerEvent] # Allowed event constructors

		window.onload = @onPageLoad # On iframe loaded
		window.onhashchange = (e) => # On hash change
			@log "Hashchange", window.location.hash
			if window.location.hash
				src = $("#inner-iframe").attr("src").replace(/#.*/, "")+window.location.hash
				$("#inner-iframe").attr("src", src)

		window.onpopstate = (e) =>
			@sendInner {"cmd": "wrapperPopState", "params": {"href": document.location.href, "state": e.state}}

		$("#inner-iframe").focus()


	verifyEvent: (allowed_target, e) =>
		if not e.originalEvent.isTrusted
			throw "Event not trusted"

		if e.originalEvent.constructor not in @allowed_event_constructors
			throw "Invalid event constructor: #{e.constructor} not in #{JSON.stringify(@allowed_event_constructors)}"

		if e.originalEvent.currentTarget != allowed_target[0]
			throw "Invalid event target: #{e.originalEvent.currentTarget} != #{allowed_target[0]}"

	# Incoming message from UiServer websocket
	onMessageWebsocket: (e) =>
		message = JSON.parse(e.data)
		@handleMessageWebsocket(message)

	handleMessageWebsocket: (message) =>
		cmd = message.cmd
		if cmd == "response"
			if @ws.waiting_cb[message.to]? # We are waiting for response
				@ws.waiting_cb[message.to](message.result)
			else
				@sendInner message # Pass message to inner frame
		else if cmd == "notification" # Display notification
			type = message.params[0]
			id = "notification-ws-#{message.id}"
			if "-" in message.params[0]  # - in first param: message id defined
				[id, type] = message.params[0].split("-")
			@notifications.add(id, type, message.params[1], message.params[2])
		else if cmd == "progress" # Display notification
			@actionProgress(message)
		else if cmd == "prompt" # Prompt input
			@displayPrompt message.params[0], message.params[1], message.params[2], message.params[3], (res) =>
				@ws.response message.id, res
		else if cmd == "confirm" # Confirm action
			@displayConfirm message.params[0], message.params[1], (res) =>
				@ws.response message.id, res
		else if cmd == "setSiteInfo"
			@sendInner message # Pass to inner frame
			if message.params.address == @address # Current page
				@setSiteInfo message.params
			@updateProgress message.params
		else if cmd == "setAnnouncerInfo"
			@sendInner message # Pass to inner frame
			if message.params.address == @address # Current page
				@setAnnouncerInfo message.params
			@updateProgress message.params
		else if cmd == "error"
			@notifications.add("notification-#{message.id}", "error", message.params, 0)
		else if cmd == "updating" # Close connection
			@log "Updating: Closing websocket"
			@ws.ws.close()
			@ws.onCloseWebsocket(null, 4000)
		else if cmd == "redirect"
			window.top.location = message.params
		else if cmd == "injectHtml"
			$("body").append(message.params)
		else if cmd == "injectScript"
			script_tag = $("<script>")
			script_tag.attr("nonce", @script_nonce)
			script_tag.html(message.params)
			document.head.appendChild(script_tag[0])
		else
			@sendInner message # Pass message to inner frame

	# Incoming message from inner frame
	onMessageInner: (e) =>
		# No nonce security enabled, test if window opener present
		if not window.postmessage_nonce_security and @opener_tested == false
			if window.opener and window.opener != window
				@log "Opener present", window.opener
				@displayOpenerDialog()
				return false
			else
				@opener_tested = true

		message = e.data
		# Invalid message (probably not for us)
		if not message.cmd
			@log "Invalid message:", message
			return false

		# Test nonce security to avoid third-party messages
		if window.postmessage_nonce_security and message.wrapper_nonce != window.wrapper_nonce
			@log "Message nonce error:", message.wrapper_nonce, '!=', window.wrapper_nonce
			return

		@handleMessage message

	cmd: (cmd, params={}, cb=null) =>
		message = {}
		message.cmd = cmd
		message.params = params
		message.id = @next_cmd_message_id
		if cb
			@ws.waiting_cb[message.id] = cb
		@next_cmd_message_id -= 1

		@handleMessage(message)

	handleMessage: (message) =>
		cmd = message.cmd
		if cmd == "innerReady"
			@inner_ready = true
			if @ws.ws.readyState == 1 and not @wrapperWsInited # If ws already opened
				@sendInner {"cmd": "wrapperOpenedWebsocket"}
				@wrapperWsInited = true
		else if cmd == "innerLoaded" or cmd == "wrapperInnerLoaded"
			if window.location.hash
				$("#inner-iframe")[0].src += window.location.hash # Hash tag
				@log "Added hash to location", $("#inner-iframe")[0].src
		else if cmd == "wrapperNotification" # Display notification
			@actionNotification(message)
		else if cmd == "wrapperConfirm" # Display confirm message
			@actionConfirm(message)
		else if cmd == "wrapperPrompt" # Prompt input
			@actionPrompt(message)
		else if cmd == "wrapperProgress" # Progress bar
			@actionProgress(message)
		else if cmd == "wrapperSetViewport" # Set the viewport
			@actionSetViewport(message)
		else if cmd == "wrapperSetTitle"
			$("head title").text(message.params)
		else if cmd == "wrapperReload" # Reload current page
			@actionReload(message)
		else if cmd == "wrapperGetLocalStorage"
			@actionGetLocalStorage(message)
		else if cmd == "wrapperSetLocalStorage"
			@actionSetLocalStorage(message)
		else if cmd == "wrapperPushState"
			query = @toRelativeQuery(message.params[2])
			window.history.pushState(message.params[0], message.params[1], query)
		else if cmd == "wrapperReplaceState"
			query = @toRelativeQuery(message.params[2])
			window.history.replaceState(message.params[0], message.params[1], query)
		else if cmd == "wrapperGetState"
			@sendInner {"cmd": "response", "to": message.id, "result": window.history.state}
		else if cmd == "wrapperGetAjaxKey"
			@sendInner {"cmd": "response", "to": message.id, "result": window.ajax_key}
		else if cmd == "wrapperOpenWindow"
			@actionOpenWindow(message.params)
		else if cmd == "wrapperPermissionAdd"
			@actionPermissionAdd(message)
		else if cmd == "wrapperRequestFullscreen"
			@actionRequestFullscreen()
		else if cmd == "wrapperWebNotification"
			@actionWebNotification(message)
		else if cmd == "wrapperCloseWebNotification"
			@actionCloseWebNotification(message)
		else # Send to websocket
			if message.id < 1000000
				if message.cmd == "fileWrite" and not @modified_panel_updater_timer and site_info?.settings?.own
					@modified_panel_updater_timer = setTimeout ( => @updateModifiedPanel(); @modified_panel_updater_timer = null ), 1000
				@ws.send(message) # Pass message to websocket
			else
				@log "Invalid inner message id"

	toRelativeQuery: (query=null) ->
		if query == null
			query = window.location.search
		back = window.location.pathname
		if back.match /^\/[^\/]+$/ # Add / after site address if called without it
			back += "/"
		if query.startsWith("#")
			back = query
		else if query.replace("?", "")
			back += "?"+query.replace("?", "")
		return back


	displayOpenerDialog: ->
		elem = $("<div class='opener-overlay'><div class='dialog'>You have opened this page by clicking on a link. Please, confirm if you want to load this site.<a href='?' target='_blank' class='button'>Open site</a></div></div>")
		elem.find('a').on "click", ->
			window.open("?", "_blank")
			window.close()
			return false
		$("body").prepend(elem)

	# - Actions -

	actionOpenWindow: (params) ->
		if typeof(params) == "string"
			w = window.open()
			w.opener = null
			w.location = params
		else
			w = window.open(null, params[1], params[2])
			w.opener = null
			w.location = params[0]

	actionRequestFullscreen: ->
		elem = document.getElementById("inner-iframe")
		request_fullscreen = elem.requestFullScreen || elem.webkitRequestFullscreen || elem.mozRequestFullScreen || elem.msRequestFullScreen
		request_fullscreen.call(elem)

	actionWebNotification: (message) ->
		$.when(@event_site_info).done =>
			# Check that the wrapper may send notifications
			if Notification.permission == "granted"
				@displayWebNotification message
			else if Notification.permission == "denied"
				res = {"error": "Web notifications are disabled by the user"}
				@sendInner {"cmd": "response", "to": message.id, "result": res}
			else
				Notification.requestPermission().then (permission) =>
					if permission == "granted"
						@displayWebNotification message

	actionCloseWebNotification: (message) ->
		$.when(@event_site_info).done =>
			id = message.params[0]
			@web_notifications[id].close()

	displayWebNotification: (message) ->
		title = message.params[0]
		id = message.params[1]
		options = message.params[2]
		notification = new Notification(title, options)
		@web_notifications[id] = notification
		notification.onshow = () =>
			@sendInner {"cmd": "response", "to": message.id, "result": "ok"}
		notification.onclick = (e) =>
			if not options.focus_tab
				e.preventDefault()
			@sendInner {"cmd": "webNotificationClick", "params": {"id": id}}
		notification.onclose = () =>
			@sendInner {"cmd": "webNotificationClose", "params": {"id": id}}
			delete @web_notifications[id]

	actionPermissionAdd: (message) ->
		permission = message.params
		$.when(@event_site_info).done =>
			if permission in @site_info.settings.permissions
				return false
			@ws.cmd "permissionDetails", permission, (permission_details) =>
				@displayConfirm "This site requests permission:" + " <b>#{@toHtmlSafe(permission)}</b>" + "<br><small style='color: #4F4F4F'>#{permission_details}</small>", "Grant", =>
					@ws.cmd "permissionAdd", permission, (res) =>
						@sendInner {"cmd": "response", "to": message.id, "result": res}

	actionNotification: (message) ->
		message.params = @toHtmlSafe(message.params) # Escape html
		body =  $("<span class='message'>"+message.params[1]+"</span>")
		@notifications.add("notification-#{message.id}", message.params[0], body, message.params[2])

	displayConfirm: (body, captions, cb) ->
		body = $("<span class='message-outer'><span class='message'>"+body+"</span></span>")
		buttons = $("<span class='buttons'></span>")
		if captions not instanceof Array then captions = [captions]  # Convert to list if necessary
		for caption, i in captions
			button = $("<a></a>", {href: "#" + caption, class: "button button-confirm button-#{caption} button-#{i+1}", "data-value": i + 1})  # Add confirm button
			button.text(caption)
			((button) =>
				button.on "click", (e) =>
					@verifyEvent button, e
					cb(parseInt(e.currentTarget.dataset.value))
					return false
			)(button)
			buttons.append(button)
		body.append(buttons)
		@notifications.add("notification-#{caption}", "ask", body)

		buttons.first().focus()
		$(".notification").scrollLeft(0)


	actionConfirm: (message, cb=false) ->
		message.params = @toHtmlSafe(message.params) # Escape html
		if message.params[1] then caption = message.params[1] else caption = "ok"
		@displayConfirm message.params[0], caption, (res) =>
			@sendInner {"cmd": "response", "to": message.id, "result": res} # Response to confirm
			return false


	displayPrompt: (message, type, caption, placeholder, cb) ->
		body = $("<span class='message'></span>").html(message)
		placeholder ?= ""

		input = $("<input/>", {type: type, class: "input button-#{type}", placeholder: placeholder}) # Add input
		input.on "keyup", (e) => # Send on enter
			@verifyEvent input, e
			if e.keyCode == 13
				cb input.val() # Response to confirm
		body.append(input)

		button = $("<a></a>", {href: "#" + caption, class: "button button-#{caption}"}).text(caption) # Add confirm button
		button.on "click", (e) => # Response on button click
			@verifyEvent button, e
			cb input.val()
			return false
		body.append(button)

		@notifications.add("notification-#{message.id}", "ask", body)

		input.focus()
		$(".notification").scrollLeft(0)


	actionPrompt: (message) ->
		message.params = @toHtmlSafe(message.params) # Escape html
		if message.params[1] then type = message.params[1] else type = "text"
		caption = if message.params[2] then message.params[2] else "OK"
		if message.params[3]?
			placeholder = message.params[3]
		else
			placeholder = ""

		@displayPrompt message.params[0], type, caption, placeholder, (res) =>
			@sendInner {"cmd": "response", "to": message.id, "result": res} # Response to confirm

	displayProgress: (type, body, percent) ->
		percent = Math.min(100, percent)/100
		offset = 75-(percent*75)
		circle = """
			<div class="circle"><svg class="circle-svg" width="30" height="30" viewport="0 0 30 30" version="1.1" xmlns="http://www.w3.org/2000/svg">
  				<circle r="12" cx="15" cy="15" fill="transparent" class="circle-bg"></circle>
  				<circle r="12" cx="15" cy="15" fill="transparent" class="circle-fg" style="stroke-dashoffset: #{offset}"></circle>
			</svg></div>
		"""
		body = "<span class='message'>"+body+"</span>" + circle
		elem = $(".notification-#{type}")
		if elem.length
			width = $(".body .message", elem).outerWidth()
			$(".body .message", elem).html(body)
			if $(".body .message", elem).css("width") == ""
				$(".body .message", elem).css("width", width)
			$(".body .circle-fg", elem).css("stroke-dashoffset", offset)
		else
			elem = @notifications.add(type, "progress", $(body))
		if percent > 0
			$(".body .circle-bg", elem).css {"animation-play-state": "paused", "stroke-dasharray": "180px"}

		if $(".notification-icon", elem).data("done")
			return false
		else if percent >= 1  # Done
			$(".circle-fg", elem).css("transition", "all 0.3s ease-in-out")
			setTimeout (->
				$(".notification-icon", elem).css {transform: "scale(1)", opacity: 1}
				$(".notification-icon .icon-success", elem).css {transform: "rotate(45deg) scale(1)"}
			), 300
			setTimeout (=>
				@notifications.close elem
			), 3000
			$(".notification-icon", elem).data("done", true)
		else if percent < 0  # Error
			$(".body .circle-fg", elem).css("stroke", "#ec6f47").css("transition", "transition: all 0.3s ease-in-out")
			setTimeout (=>
				$(".notification-icon", elem).css {transform: "scale(1)", opacity: 1}
				elem.removeClass("notification-done").addClass("notification-error")
				$(".notification-icon .icon-success", elem).removeClass("icon-success").html("!")
			), 300
			$(".notification-icon", elem).data("done", true)


	actionProgress: (message) ->
		message.params = @toHtmlSafe(message.params) # Escape html
		@displayProgress(message.params[0], message.params[1], message.params[2])

	actionSetViewport: (message) ->
		@log "actionSetViewport", message
		if $("#viewport").length > 0
			$("#viewport").attr("content", @toHtmlSafe message.params)
		else
			$('<meta name="viewport" id="viewport">').attr("content", @toHtmlSafe message.params).appendTo("head")

	actionReload: (message) ->
		@reload(message.params[0])

	reload: (url_post="") ->
		if url_post
			if window.location.toString().indexOf("?") > 0
				window.location += "&"+url_post
			else
				window.location += "?"+url_post
		else
			window.location.reload()


	actionGetLocalStorage: (message) ->
		$.when(@event_site_info).done =>
			data = localStorage.getItem "site.#{@site_info.address}.#{@site_info.auth_address}"
			if not data # Migrate from non auth_address based local storage
				data = localStorage.getItem "site.#{@site_info.address}"
				if data
					localStorage.setItem "site.#{@site_info.address}.#{@site_info.auth_address}", data
					localStorage.removeItem "site.#{@site_info.address}"
					@log "Migrated LocalStorage from global to auth_address based"
			if data then data = JSON.parse(data)
			@sendInner {"cmd": "response", "to": message.id, "result": data}


	actionSetLocalStorage: (message) ->
		$.when(@event_site_info).done =>
			back = localStorage.setItem "site.#{@site_info.address}.#{@site_info.auth_address}", JSON.stringify(message.params)
			@sendInner {"cmd": "response", "to": message.id, "result": back}


	# EOF actions


	onOpenWebsocket: (e) =>
		if window.show_loadingscreen   # Get info on modifications
			@ws.cmd "channelJoin", {"channels": ["siteChanged", "serverChanged", "announcerChanged"]}
		else
			@ws.cmd "channelJoin", {"channels": ["siteChanged", "serverChanged"]}
		if not @wrapperWsInited and @inner_ready
			@sendInner {"cmd": "wrapperOpenedWebsocket"} # Send to inner frame
			@wrapperWsInited = true
		if window.show_loadingscreen
			@ws.cmd "serverInfo", [], (server_info) =>
				@server_info = server_info

			@ws.cmd "announcerInfo", [], (announcer_info) =>
				@setAnnouncerInfo(announcer_info)

		if @inner_loaded # Update site info
			@reloadSiteInfo()

		# If inner frame not loaded for 2 sec show peer informations on loading screen by loading site info
		setTimeout (=>
			if not @site_info then @reloadSiteInfo()
		), 2000

		if @ws_error
			@notifications.add("connection", "done", "Connection with <b>UiServer Websocket</b> recovered.", 6000)
			@ws_error = null


	onCloseWebsocket: (e) =>
		@wrapperWsInited = false
		setTimeout (=> # Wait a bit, maybe its page closing
			@sendInner {"cmd": "wrapperClosedWebsocket"} # Send to inner frame
			if e and e.code == 1000 and e.wasClean == false # Server error please reload page
				@ws_error = @notifications.add("connection", "error", "UiServer Websocket error, please reload the page.")
			else if e and e.code == 1001 and e.wasClean == true  # Navigating to other page
				return
			else if not @ws_error
				@ws_error = @notifications.add("connection", "error", "Connection with <b>UiServer Websocket</b> was lost. Reconnecting...")
		), 1000


	# Iframe loaded
	onPageLoad: (e) =>
		@inner_loaded = true
		if not @inner_ready then @sendInner {"cmd": "wrapperReady"} # Inner frame loaded before wrapper
		#if not @site_error then @loading.hideScreen() # Hide loading screen
		if @ws.ws.readyState == 1 and not @site_info # Ws opened
			@reloadSiteInfo()
		else if @site_info and @site_info.content?.title?
			window.document.title = @site_info.content.title+" - ZeroNet"
			@log "Setting title to", window.document.title

	onWrapperLoad: =>
		@script_nonce = window.script_nonce
		@wrapper_key = window.wrapper_key
		# Cleanup secret variables
		delete window.wrapper
		delete window.wrapper_key
		delete window.script_nonce
		$("#script_init").remove()

	# Send message to innerframe
	sendInner: (message) ->
		@inner.postMessage(message, '*')


	# Get site info from UiServer
	reloadSiteInfo: ->
		if @loading.screen_visible # Loading screen visible
			params = {"file_status": window.file_inner_path} # Query the current required file status
		else
			params = {}

		@ws.cmd "siteInfo", params, (site_info) =>
			@address = site_info.address
			@setSiteInfo site_info

			if site_info.settings.size > site_info.size_limit*1024*1024 # Site size too large and not displaying it yet
				if @loading.screen_visible
					@loading.showTooLarge(site_info)
				else
					@displayConfirm "Site is larger than allowed: #{(site_info.settings.size/1024/1024).toFixed(1)}MB/#{site_info.size_limit}MB", "Set limit to #{site_info.next_size_limit}MB", =>
						@ws.cmd "siteSetLimit", [site_info.next_size_limit], (res) =>
							if res == "ok"
								@notifications.add("size_limit", "done", "Site storage limit modified!", 5000)

			if site_info.content?.title?
				window.document.title = site_info.content.title + " - ZeroNet"
				@log "Setting title to", window.document.title


	# Got setSiteInfo from websocket UiServer
	setSiteInfo: (site_info) ->
		if site_info.event? # If loading screen visible add event to it
			# File started downloading
			if site_info.event[0] == "file_added" and site_info.bad_files
				@loading.printLine("#{site_info.bad_files} files needs to be downloaded")
			# File finished downloading
			else if site_info.event[0] == "file_done"
				@loading.printLine("#{site_info.event[1]} downloaded")
				if site_info.event[1] == window.file_inner_path # File downloaded we currently on
					@loading.hideScreen()
					if not @site_info then @reloadSiteInfo()
					if site_info.content
						window.document.title = site_info.content.title+" - ZeroNet"
						@log "Required file done, setting title to", window.document.title
					if not window.show_loadingscreen
						@notifications.add("modified", "info", "New version of this page has just released.<br>Reload to see the modified content.")
			# File failed downloading
			else if site_info.event[0] == "file_failed"
				@site_error = site_info.event[1]
				if site_info.settings.size > site_info.size_limit*1024*1024 # Site size too large and not displaying it yet
					@loading.showTooLarge(site_info)

				else
					@loading.printLine("#{site_info.event[1]} download failed", "error")
			# New peers found
			else if site_info.event[0] == "peers_added"
				@loading.printLine("Peers found: #{site_info.peers}")

		if @loading.screen_visible and not @site_info # First site info display current peers
			if site_info.peers > 1
				@loading.printLine "Peers found: #{site_info.peers}"
			else
				@site_error = "No peers found"
				@loading.printLine "No peers found"

		if not @site_info and not @loading.screen_visible and $("#inner-iframe").attr("src").replace("?wrapper=False", "").replace(/\?wrapper_nonce=[A-Za-z0-9]+/, "").indexOf("?") == -1 # First site info and we are on mainpage (does not have other parameter thatn wrapper)
			if site_info.size_limit*1.1 < site_info.next_size_limit # Need upgrade soon
				@displayConfirm "Running out of size limit (#{(site_info.settings.size/1024/1024).toFixed(1)}MB/#{site_info.size_limit}MB)", "Set limit to #{site_info.next_size_limit}MB", =>
					@ws.cmd "siteSetLimit", [site_info.next_size_limit], (res) =>
						if res == "ok"
							@notifications.add("size_limit", "done", "Site storage limit modified!", 5000)
					return false

		if @loading.screen_visible and @inner_loaded and site_info.settings.size < site_info.size_limit*1024*1024 and site_info.settings.size > 0 # Loading screen still visible, but inner loaded
			@loading.hideScreen()

		if site_info?.settings?.own and site_info?.settings?.modified != @site_info?.settings?.modified
			@updateModifiedPanel()

		@site_info = site_info
		@event_site_info.resolve()

	siteSign: (inner_path, cb) =>
		if @site_info.privatekey
			# Privatekey stored in users.json
			@infopanel.elem.find(".button").addClass("loading")
			@ws.cmd "siteSign", {privatekey: "stored", inner_path: inner_path, update_changed_files: true}, (res) =>
				if res == "ok"
					cb?(true)
				else
					cb?(false)
				@infopanel.elem.find(".button").removeClass("loading")
		else
			# Ask the user for privatekey
			@displayPrompt "Enter your private key:", "password", "Sign", "", (privatekey) => # Prompt the private key
				@infopanel.elem.find(".button").addClass("loading")
				@ws.cmd "siteSign", {privatekey: privatekey, inner_path: inner_path, update_changed_files: true}, (res) =>
					if res == "ok"
						cb?(true)
					else
						cb?(false)
					@infopanel.elem.find(".button").removeClass("loading")

	sitePublish: (inner_path) =>
		@ws.cmd "sitePublish", {"inner_path": inner_path, "sign": false}

	updateModifiedPanel: =>
		@ws.cmd "siteListModifiedFiles", [], (res) =>
			num = res.modified_files.length
			if num > 0
				closed = @site_info.settings.modified_files_notification == false
				@infopanel.show(closed)
			else
				@infopanel.hide()

			if num > 0
				@infopanel.setTitle(
					"#{res.modified_files.length} modified file#{if num > 1 then 's' else ''}",
					res.modified_files.join(", ")
				)
				@infopanel.setClosedNum(num)
				@infopanel.setAction "Sign & Publish", =>
					@siteSign "content.json", (res) =>
						if (res)
							@notifications.add "sign", "done", "content.json Signed!", 5000
							@sitePublish("content.json")
					return false

			@log "siteListModifiedFiles", res

	setAnnouncerInfo: (announcer_info) ->
		status_db = {announcing: [], error: [], announced: []}
		for key, val of announcer_info.stats
			if val.status
				status_db[val.status].push(val)
		status_line = "Trackers announcing: #{status_db.announcing.length}, error: #{status_db.error.length}, done: #{status_db.announced.length}"
		if @announcer_line
			@announcer_line.text(status_line)
		else
			@announcer_line = @loading.printLine(status_line)

		if status_db.error.length > (status_db.announced.length + status_db.announcing.length)
			@loading.showTrackerTorBridge(@server_info)

	updateProgress: (site_info) ->
		if site_info.tasks > 0 and site_info.started_task_num > 0
			@loading.setProgress 1-(Math.max(site_info.tasks, site_info.bad_files) / site_info.started_task_num)
		else
			@loading.hideProgress()


	toHtmlSafe: (values) ->
		if values not instanceof Array then values = [values] # Convert to array if its not
		for value, i in values
			if value instanceof Array
				value = @toHtmlSafe(value)
			else
				value = String(value).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&apos;') # Escape dangerous characters
				value = value.replace(/&lt;([\/]{0,1}(br|b|u|i|small))&gt;/g, "<$1>") # Unescape b, i, u, br tags
			values[i] = value
		return values


	setSizeLimit: (size_limit, reload=true) =>
		@ws.cmd "siteSetLimit", [size_limit], (res) =>
			if res != "ok"
				return false
			@loading.printLine res
			@inner_loaded = false # Inner frame not loaded, just a 404 page displayed
			if reload then @reloadIframe()
		return false

	reloadIframe: =>
		src = $("iframe").attr("src")
		@ws.cmd "serverGetWrapperNonce", [], (wrapper_nonce) =>
			src = src.replace(/wrapper_nonce=[A-Za-z0-9]+/, "wrapper_nonce=" + wrapper_nonce)
			@log "Reloading iframe using url", src
			$("iframe").attr "src", src

	log: (args...) ->
		console.log "[Wrapper]", args...

origin = window.server_url or window.location.href.replace(/(\:\/\/.*?)\/.*/, "$1")

if origin.indexOf("https:") == 0
	proto = { ws: 'wss', http: 'https' }
else
	proto = { ws: 'ws', http: 'http' }

ws_url = proto.ws + ":" + origin.replace(proto.http+":", "") + "/ZeroNet-Internal/Websocket?wrapper_key=" + window.wrapper_key

window.wrapper = new Wrapper(ws_url)

