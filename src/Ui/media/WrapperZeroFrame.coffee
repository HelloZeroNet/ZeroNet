class WrapperZeroFrame
	constructor: (wrapper) ->
		@wrapperCmd = wrapper.cmd
		@wrapperResponse = wrapper.ws.response
		console.log "WrapperZeroFrame", wrapper

	cmd: (cmd, params={}, cb=null) =>
		@wrapperCmd(cmd, params, cb)

	response: (to, result) =>
		@wrapperResponse(to, result)

	isProxyRequest: ->
		return window.location.pathname == "/"

	certSelectGotoSite: (elem) =>
		href = $(elem).attr("href")
		if @isProxyRequest() # Fix for proxy request
			$(elem).attr("href", "http://zero#{href}")


window.zeroframe = new WrapperZeroFrame(window.wrapper)
