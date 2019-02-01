class Infopanel
	constructor: (@elem) ->
		@visible = false

	show: ->
		@elem.addClass("visible")

	hide: ->
		@elem.removeClass("visible")

	setTitle: (line1, line2) ->
		@elem.find(".line-1").text(line1)
		@elem.find(".line-2").text(line2)

	setAction: (title, func) ->
		@elem.find(".button").text(title).off("click").on("click", func)

window.Infopanel = Infopanel
