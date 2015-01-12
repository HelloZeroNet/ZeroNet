class Wrapper
	constructor: (ws_url) ->
		@log "Created!"

		@loading = new Loading()
		@notifications = new Notifications($(".notifications"))
		@sidebar = new Sidebar()

		window.addEventListener("message", @onMessageInner, false)
		@inner = document.getElementById("inner-iframe").contentWindow
		@ws = new ZeroWebsocket(ws_url)
		@ws.next_message_id = 1000000 # Avoid messageid collision :)
		@ws.onOpen = @onOpenWebsocket
		@ws.onClose = @onCloseWebsocket
		@ws.onMessage = @onMessageWebsocket
		@ws.connect()
		@ws_error = null # Ws error message

		@site_info = null # Hold latest site info
		@inner_loaded = false # If iframe loaded or not
		@inner_ready = false # Inner frame ready to receive messages
		@wrapperWsInited = false # Wrapper notified on websocket open
		@site_error = null # Latest failed file download

		window.onload = @onLoad # On iframe loaded
		@


	# Incoming message from UiServer websocket
	onMessageWebsocket: (e) =>
		message = JSON.parse(e.data)
		cmd = message.cmd
		if cmd == "response"
			if @ws.waiting_cb[message.to]? # We are waiting for response
				@ws.waiting_cb[message.to](message.result)
			else
				@sendInner message # Pass message to inner frame
		else if cmd == "notification" # Display notification
			@notifications.add("notification-#{message.id}", message.params[0], message.params[1], message.params[2])
		else if cmd == "setSiteInfo"
			@sendInner message # Pass to inner frame
			if message.params.address == window.address # Current page
				@setSiteInfo message.params
		else
			@sendInner message # Pass message to inner frame


	# Incoming message from inner frame
	onMessageInner: (e) =>
		message = e.data
		cmd = message.cmd
		if cmd == "innerReady"
			@inner_ready = true
			@log "innerReady", @ws.ws.readyState, @wrapperWsInited
			if @ws.ws.readyState == 1 and not @wrapperWsInited # If ws already opened
				@sendInner {"cmd": "wrapperOpenedWebsocket"}
				@wrapperWsInited = true
		else if cmd == "wrapperNotification"
			@notifications.add("notification-#{message.id}", message.params[0], message.params[1], message.params[2])
		else # Send to websocket
			@ws.send(message) # Pass message to websocket


	onOpenWebsocket: (e) =>
		@ws.cmd "channelJoin", {"channel": "siteChanged"} # Get info on modifications
		@log "onOpenWebsocket", @inner_ready, @wrapperWsInited
		if not @wrapperWsInited and @inner_ready
			@sendInner {"cmd": "wrapperOpenedWebsocket"} # Send to inner frame
			@wrapperWsInited = true
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
			if e.code == 1000 # Server error please reload page
				@ws_error = @notifications.add("connection", "error", "UiServer Websocket error, please reload the page.")
			else if not @ws_error
				@ws_error = @notifications.add("connection", "error", "Connection with <b>UiServer Websocket</b> was lost. Reconnecting...")
		), 500


	# Iframe loaded
	onLoad: (e) =>
		@log "onLoad", e
		@inner_loaded = true
		if not @inner_ready then @sendInner {"cmd": "wrapperReady"} # Inner frame loaded before wrapper
		if not @site_error then @loading.hideScreen() # Hide loading screen
		if @ws.ws.readyState == 1 and not @site_info # Ws opened
			@reloadSiteInfo()


	# Send message to innerframe
	sendInner: (message) ->
		@inner.postMessage(message, '*')


	# Get site info from UiServer
	reloadSiteInfo: ->
		@ws.cmd "siteInfo", {}, (site_info) =>
			@setSiteInfo site_info
			window.document.title = site_info.content.title+" - ZeroNet"
			@log "Setting title to", window.document.title


	# Got setSiteInfo from websocket UiServer
	setSiteInfo: (site_info) ->
		if site_info.event? # If loading screen visible add event to it
			# File started downloading
			if site_info.event[0] == "file_added" and site_info.bad_files.length
				@loading.printLine("#{site_info.bad_files.length} files needs to be downloaded")
			# File finished downloading
			else if site_info.event[0] == "file_done"
				@loading.printLine("#{site_info.event[1]} downloaded")
				if site_info.event[1] == window.inner_path # File downloaded we currently on
					@loading.hideScreen()
					if not $(".loadingscreen").length # Loading screen already removed (loaded +2sec)
						@notifications.add("modified", "info", "New version of this page has just released.<br>Reload to see the modified content.")
			# File failed downloading
			else if site_info.event[0] == "file_failed" 
				@site_error = site_info.event[1]
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
		@site_info = site_info


	log: (args...) ->
		console.log "[Wrapper]", args...


ws_url = "ws://#{window.location.hostname}:#{window.location.port}/Websocket?auth_key=#{window.auth_key}"
window.wrapper = new Wrapper(ws_url)
