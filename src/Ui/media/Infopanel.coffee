class Infopanel
	constructor: (@elem) ->
		@visible = false

	show: (closed=false) =>
		@elem.addClass("visible")
		if closed
			@close()
		else
			@open()

	updateEvents: =>
		@elem.off("click")
		@elem.find(".close").off("click")

		if @elem.hasClass("closed")
			@elem.on "click", =>
				@onOpened()
				@open()
		else
			@elem.find(".close").on "click", =>
				@onClosed()
				@close()

	hide: =>
		@elem.removeClass("visible")

	close: =>
		@elem.addClass("closed")
		@updateEvents()
		return false

	open: =>
		@elem.removeClass("closed")
		@updateEvents()
		return false

	setTitle: (line1, line2) =>
		@elem.find(".line-1").text(line1)
		@elem.find(".line-2").text(line2)

	setClosedNum: (num) =>
		@elem.find(".closed-num").text(num)

	setAction: (title, func) =>
		@elem.find(".button").text(title).off("click").on("click", func)



window.Infopanel = Infopanel
