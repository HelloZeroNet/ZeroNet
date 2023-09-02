class Notifications
	constructor: (@elem) ->
		@

	test: ->
		setTimeout (=>
			@add("connection", "error", "Connection lost to <b>UiServer</b> on <b>localhost</b>!")
			@add("message-Anyone", "info", "New  from <b>Anyone</b>.")
		), 1000
		setTimeout (=>
			@add("connection", "done", "<b>UiServer</b> connection recovered.", 5000)
		), 3000


	add: (id, type, body, timeout=0) ->
		id = id.replace /[^A-Za-z0-9-]/g, ""
		# Close notifications with same id
		for elem in $(".notification-#{id}")
			@close $(elem)

		# Create element
		elem = $(".notification.template", @elem).clone().removeClass("template")
		elem.addClass("notification-#{type}").addClass("notification-#{id}")
		if type == "progress"
			elem.addClass("notification-done")

		# Update text
		if type == "error"
			$(".notification-icon", elem).html("!")
		else if type == "done"
			$(".notification-icon", elem).html("<div class='icon-success'></div>")
		else if type == "progress"
			$(".notification-icon", elem).html("<div class='icon-success'></div>")
		else if type == "ask"
			$(".notification-icon", elem).html("?")
		else
			$(".notification-icon", elem).html("i")

		if typeof(body) == "string"
			$(".body", elem).html("<div class='message'><span class='multiline'>"+body+"</span></div>")
		else
			$(".body", elem).html("").append(body)

		elem.appendTo(@elem)

		# Timeout
		if timeout
			$(".close", elem).remove() # No need of close button
			setTimeout (=>
				@close elem
			), timeout

		# Animate
		width = Math.min(elem.outerWidth() + 50, 580)
		if not timeout then width += 20 # Add space for close button
		if elem.outerHeight() > 55 then elem.addClass("long")
		elem.css({"width": "50px", "transform": "scale(0.01)"})
		elem.animate({"scale": 1}, 800, "easeOutElastic")
		elem.animate({"width": width}, 700, "easeInOutCubic")
		$(".body", elem).css("width": (width - 50))
		$(".body", elem).cssLater("box-shadow", "0px 0px 5px rgba(0,0,0,0.1)", 1000)

		# Close button or Confirm button
		$(".close, .button", elem).on "click", =>
			@close elem
			return false

		# Select list
		$(".select", elem).on "click", =>
			@close elem

		# Input enter
		$("input", elem).on "keyup", (e) =>
			if e.keyCode == 13
				@close elem

		return elem


	close: (elem) ->
		elem.stop().animate {"width": 0, "opacity": 0}, 700, "easeInOutCubic"
		elem.slideUp 300, (-> elem.remove())


	log: (args...) ->
		console.log "[Notifications]", args...


window.Notifications = Notifications
