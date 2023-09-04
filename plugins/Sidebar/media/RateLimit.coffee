limits = {}
call_after_interval = {}
window.RateLimit = (interval, fn) ->
	if not limits[fn]
		call_after_interval[fn] = false
		fn() # First call is not delayed
		limits[fn] = setTimeout (->
			if call_after_interval[fn]
				fn()
			delete limits[fn]
			delete call_after_interval[fn]
		), interval
	else # Called within iterval, delay the call
		call_after_interval[fn] = true
