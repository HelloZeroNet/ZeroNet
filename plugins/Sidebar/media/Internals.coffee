class Internals extends Class
	constructor: (@sidebar) ->
		@tag = null
		@opened = false
		if window.top.location.hash == "#internals"
			setTimeout (=> @open()), 10

	createHtmltag: ->
		@when_loaded = $.Deferred()
		if not @container
			@container = $("""
			<div class="internals-container">
				<div class="internals"><div class="internals-middle">
					<div class="mynode"></div>
					<div class="peers">
						<div class="peer"><div class="line"></div><a href="#" class="icon">\u25BD</div></div>
					</div>
				</div></div>
			</div>
			""")
			@container.appendTo(document.body)
			@tag = @container.find(".internals")

	open: =>
		@createHtmltag()
		@sidebar.fixbutton_targety = @sidebar.page_height
		@stopDragY()

	onOpened: =>
		@sidebar.onClosed()
		@log "onOpened"

	onClosed: =>
		$(document.body).removeClass("body-internals")

	stopDragY: =>
		# Animate sidebar and iframe
		if @sidebar.fixbutton_targety == @sidebar.fixbutton_inity
			# Closed
			targety = 0
			@opened = false
		else
			# Opened
			targety = @sidebar.fixbutton_targety - @sidebar.fixbutton_inity
			@onOpened()
			@opened = true

		# Revent sidebar transitions
		if @tag
			@tag.css("transition", "0.5s ease-out")
			@tag.css("transform", "translateY(#{targety}px)").one transitionEnd, =>
				@tag.css("transition", "")
				if not @opened
					@log "cleanup"
		# Revert body transformations
		@log "stopdrag", "opened:", @opened, targety
		if not @opened
			@onClosed()

window.Internals = Internals