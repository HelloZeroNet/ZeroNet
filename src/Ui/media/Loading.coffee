class Loading
	constructor: ->
		if window.show_loadingscreen then @showScreen()


	setProgress: (percent) ->
		$(".progressbar").css("width", percent*100+"%").css("opacity", "1").css("display", "block")

	hideProgress: ->
		console.log "hideProgress"
		$(".progressbar").css("width", "100%").css("opacity", "0").hideLater(1000)


	showScreen: ->
		$(".loadingscreen").css("display", "block").addClassLater("ready")
		@screen_visible = true
		@printLine "&nbsp;&nbsp;&nbsp;Connecting..."


	showTooLarge: (site_info) ->
		if $(".console .button-setlimit").length == 0 # Not displaying it yet
			line = @printLine("Site size: <b>#{parseInt(site_info.settings.size/1024/1024)}MB</b> is larger than default allowed #{parseInt(site_info.size_limit)}MB", "warning")
			button = $("<a href='#Set+limit' class='button button-setlimit'>Open site and set size limit to #{site_info.next_size_limit}MB</a>")
			button.on "click", (-> return window.wrapper.setSizeLimit(site_info.next_size_limit) )
			line.after(button)
			setTimeout (=>
				@printLine('Ready.')
			), 100



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