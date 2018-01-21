class Menu
	constructor: (@button) ->
		@elem = $(".menu.template").clone().removeClass("template")
		@elem.appendTo("body")
		@items = []

	show: ->
		if window.visible_menu and window.visible_menu.button[0] == @button[0] # Same menu visible then hide it
			window.visible_menu.hide()
			@hide()
		else
			button_pos = @button.offset()
			left = button_pos.left
			@elem.css({"top": button_pos.top+@button.outerHeight(), "left": left})
			@button.addClass("menu-active")
			@elem.addClass("visible")
			if @elem.position().left + @elem.width() + 20 > window.innerWidth
				@elem.css("left", window.innerWidth - @elem.width() - 20)
			if window.visible_menu then window.visible_menu.hide()
			window.visible_menu = @


	hide: ->
		@elem.removeClass("visible")
		@button.removeClass("menu-active")
		window.visible_menu = null


	addItem: (title, cb) ->
		item = $(".menu-item.template", @elem).clone().removeClass("template")
		item.html(title)
		item.on "click", =>
			if not cb(item)
				@hide()
			return false
		item.appendTo(@elem)
		@items.push item
		return item


	log: (args...) ->
		console.log "[Menu]", args...

window.Menu = Menu

# Hide menu on outside click
$("body").on "click", (e) ->
	if window.visible_menu and e.target != window.visible_menu.button[0] and $(e.target).parent()[0] != window.visible_menu.elem[0]
		window.visible_menu.hide()
