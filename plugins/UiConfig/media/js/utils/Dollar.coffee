window.$ = (selector) ->
	if selector.startsWith("#")
		return document.getElementById(selector.replace("#", ""))
