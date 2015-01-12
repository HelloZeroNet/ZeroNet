class Loading
	constructor: ->
		if window.show_loadingscreen then @showScreen()


	showScreen: ->
		$(".loadingscreen").css("display", "block").addClassLater("ready")
		@screen_visible = true
		@printLine "&nbsp;&nbsp;&nbsp;Connecting..."



	# We dont need loadingscreen anymore
	hideScreen: ->
		if not $(".loadingscreen").hasClass("done") # Nothing to do, just let the animtion to be finished
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
		$(".loadingscreen .console").append("<div class='console-line'>#{text}</div>")



window.Loading = Loading