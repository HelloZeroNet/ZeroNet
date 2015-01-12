class ZeroWebsocket
	constructor: (url) ->
		@url = url
		@next_message_id = 1
		@waiting_cb = {}
		@init()


	init: ->
		@


	connect: ->
		@ws = new WebSocket(@url)
		@ws.onmessage = @onMessage
		@ws.onopen = @onOpenWebsocket
		@ws.onerror = @onErrorWebsocket
		@ws.onclose = @onCloseWebsocket


	onMessage: (e) =>
		message = JSON.parse(e.data)
		cmd = message.cmd
		if cmd == "response"
			if @waiting_cb[message.to]?
				@waiting_cb[message.to](message.result)
			else
				@log "Websocket callback not found:", message
		else if cmd == "ping"
			@response message.id, "pong"
		else
			@route cmd, message

	route: (cmd, message) =>
		@log "Unknown command", message


	response: (to, result) ->
		@send {"cmd": "response", "to": to, "result": result}


	cmd: (cmd, params={}, cb=null) ->
		@send {"cmd": cmd, "params": params}, cb


	send: (message, cb=null) ->
		if not message.id?
			message.id = @next_message_id
			@next_message_id += 1
		@ws.send(JSON.stringify(message))
		if cb
			@waiting_cb[message.id] = cb


	log: (args...) =>
		console.log "[ZeroWebsocket]", args...


	onOpenWebsocket: (e) =>
		@log "Open", e
		if @onOpen? then @onOpen(e)


	onErrorWebsocket: (e) =>
		@log "Error", e
		if @onError? then @onError(e)


	onCloseWebsocket: (e) =>
		@log "Closed", e
		if e.code == 1000
			@log "Server error, please reload the page"
		else # Connection error
			setTimeout (=>
				@log "Reconnecting..."
				@connect()
			), 10000
		if @onClose? then @onClose(e)


window.ZeroWebsocket = ZeroWebsocket
