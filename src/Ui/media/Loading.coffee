class Loading
	constructor: (@wrapper) ->
		if window.show_loadingscreen then @showScreen()
		@timer_hide = null

	setProgress: (percent) ->
		if @timer_hide
			clearInterval @timer_hide
		RateLimit 200, ->
			$(".progressbar").css("transform": "scaleX(#{parseInt(percent*100)/100})").css("opacity", "1").css("display", "block")

	hideProgress: ->
		console.log "hideProgress"
		@timer_hide = setTimeout ( =>
			$(".progressbar").css("transform": "scaleX(1)").css("opacity", "0").hideLater(1000)
		), 300


	showScreen: ->
		$(".loadingscreen").css("display", "block").addClassLater("ready")
		@screen_visible = true
		@printLine "&nbsp;&nbsp;&nbsp;Connecting..."


	showTooLarge: (site_info) ->
		if $(".console .button-setlimit").length == 0 # Not displaying it yet
			line = @printLine("Site size: <b>#{parseInt(site_info.settings.size/1024/1024)}MB</b> is larger than default allowed #{parseInt(site_info.size_limit)}MB", "warning")
			button = $("<a href='#Set+limit' class='button button-setlimit'>" + "Open site and set size limit to #{site_info.next_size_limit}MB" + "</a>")
			button.on "click", =>
				button.addClass("loading")
				return @wrapper.setSizeLimit(site_info.next_size_limit)
			line.after(button)
			setTimeout (=>
				@printLine('Ready.')
			), 100

	showTrackerTorBridge: (server_info) ->
		if $(".console .button-settrackerbridge").length == 0 and not server_info.tor_use_meek_bridges
			line = @printLine("Tracker connection error detected.", "error")
			button = $("<a href='#Enable+Tor+bridges' class='button button-settrackerbridge'>" + "Use Tor meek bridges for tracker connections" + "</a>")
			button.on "click", =>
				button.addClass("loading")
				@wrapper.ws.cmd "configSet", ["tor_use_bridges", ""]
				@wrapper.ws.cmd "configSet", ["trackers_proxy", "tor"]
				@wrapper.ws.cmd "siteUpdate", {address: @wrapper.site_info.address, announce: true}
				@wrapper.reloadIframe()
				return false
			line.after(button)
			if not server_info.tor_has_meek_bridges
				button.addClass("disabled")
				@printLine("No meek bridge support in your client, please <a href='https://github.com/HelloZeroNet/ZeroNet#how-to-join'>download the latest bundle</a>.", "warning")

	# We dont need loadingscreen anymore
	hideScreen: ->
		console.log "hideScreen"
		if not $(".loadingscreen").hasClass("done") # Only if its not animating already
			if @screen_visible # Hide with animate
				$(".loadingscreen").addClass("done").removeLater(2000)
			else # Not visible, just remove
				$(".loadingscreen").remove()
		@screen_visible = false


	# Append text to last line of loadingscreen
	print: (text, type="normal") ->
		if not @screen_visible then return false
		$(".loadingscreen .console .cursor").remove() # Remove previous cursor
		last_line = $(".loadingscreen .console .console-line:last-child")
		if type == "error" then text = "<span class='console-error'>#{text}</span>"
		last_line.html(last_line.html()+text)


	# Add line to loading screen
	printLine: (text, type="normal") ->
		if not @screen_visible then return false
		$(".loadingscreen .console .cursor").remove() # Remove previous cursor
		if type == "error" then text = "<span class='console-error'>#{text}</span>" else text = text+"<span class='cursor'> </span>"

		line = $("<div class='console-line'>#{text}</div>").appendTo(".loadingscreen .console")
		if type == "warning" then line.addClass("console-warning")
		return line



window.Loading = Loading
