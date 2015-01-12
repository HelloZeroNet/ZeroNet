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
		@log id, type, body, timeout
		# Close notifications with same id
		for elem in $(".notification-#{id}")
			@close $(elem)

		# Create element
		elem = $(".notification.template", @elem).clone().removeClass("template")
		elem.addClass("notification-#{type}").addClass("notification-#{id}")

		# Update text
		if type == "error"
			$(".notification-icon", elem).html("!")
		else if type == "done"
			$(".notification-icon", elem).html("<div class='icon-success'></div>")
		else
			$(".notification-icon", elem).html("i")

		$(".body", elem).html(body)

		elem.appendTo(@elem)

		# Timeout
		if timeout
			$(".close", elem).remove() # No need of close button
			setTimeout (=>
				@close elem
			), timeout

		# Animate
		width = elem.outerWidth()
		if not timeout then width += 20 # Add space for close button
		elem.css({"width": "50px", "transform": "scale(0.01)"})
		elem.animate({"scale": 1}, 800, "easeOutElastic")
		elem.animate({"width": width}, 700, "easeInOutCubic")

		# Close button
		$(".close", elem).on "click", =>
			@close elem
			return false

		@


	close: (elem) ->
		elem.stop().animate {"width": 0, "opacity": 0}, 700, "easeInOutCubic"
		elem.slideUp 300, (-> elem.remove())


	log: (args...) ->
		console.log "[Notifications]", args...


window.Notifications = Notifications