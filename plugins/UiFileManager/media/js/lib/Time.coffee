class Time
	since: (timestamp) ->
		now = +(new Date)/1000
		if timestamp > 1000000000000  # In ms
			timestamp = timestamp/1000
		secs = now - timestamp
		if secs < 60
			back = "Just now"
		else if secs < 60*60
			minutes = Math.round(secs/60)
			back = "" + minutes + " minutes ago"
		else if secs < 60*60*24
			back = "#{Math.round(secs/60/60)} hours ago"
		else if secs < 60*60*24*3
			back = "#{Math.round(secs/60/60/24)} days ago"
		else
			back = "on "+@date(timestamp)
		back = back.replace(/^1 ([a-z]+)s/, "1 $1") # 1 days ago fix
		return back

	dateIso: (timestamp=null) ->
		if not timestamp
			timestamp = window.Time.timestamp()

		if timestamp > 1000000000000  # In ms
			timestamp = timestamp/1000
		tzoffset = (new Date()).getTimezoneOffset() * 60
		return (new Date((timestamp - tzoffset) * 1000)).toISOString().split("T")[0]

	date: (timestamp=null, format="short") ->
		if not timestamp
			timestamp = window.Time.timestamp()

		if timestamp > 1000000000000  # In ms
			timestamp = timestamp/1000
		parts = (new Date(timestamp * 1000)).toString().split(" ")
		if format == "short"
			display = parts.slice(1, 4)
		else if format == "day"
			display = parts.slice(1, 3)
		else if format == "month"
			display = [parts[1], parts[3]]
		else if format == "long"
			display = parts.slice(1, 5)
		return display.join(" ").replace(/( [0-9]{4})/, ",$1")

	weekDay: (timestamp) ->
		if timestamp > 1000000000000  # In ms
			timestamp = timestamp/1000
		return ["Sunday","Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"][ (new Date(timestamp * 1000)).getDay() ]

	timestamp: (date="") ->
		if date == "now" or date == ""
			return parseInt(+(new Date)/1000)
		else
			return parseInt(Date.parse(date)/1000)


window.Time = new Time