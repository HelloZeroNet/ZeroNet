jQuery.fn.readdClass = (class_name) ->
	elem = @
	elem.removeClass class_name
	setTimeout ( ->
		elem.addClass class_name
	), 1
	return @

jQuery.fn.removeLater = (time = 500) ->
	elem = @
	setTimeout ( ->
		elem.remove()
	), time
	return @

jQuery.fn.hideLater = (time = 500) ->
	elem = @
	setTimeout ( ->
		elem.css("display", "none")
	), time
	return @

jQuery.fn.addClassLater = (class_name, time = 5) ->
	elem = @
	setTimeout ( ->
		elem.addClass(class_name)
	), time
	return @

jQuery.fn.cssLater = (name, val, time = 500) ->
	elem = @
	setTimeout ( ->
		elem.css name, val
	), time
	return @