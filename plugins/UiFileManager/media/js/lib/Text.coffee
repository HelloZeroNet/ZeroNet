class Text
	toColor: (text, saturation=30, lightness=50) ->
		hash = 0
		for i in [0..text.length-1]
			hash += text.charCodeAt(i)*i
			hash = hash % 1777
		return "hsl(" + (hash % 360) + ",#{saturation}%,#{lightness}%)";


	renderMarked: (text, options={}) ->
		options["gfm"] = true
		options["breaks"] = true
		options["sanitize"] = true
		options["renderer"] = marked_renderer
		text = marked(text, options)
		return @fixHtmlLinks text

	emailLinks: (text) ->
		return text.replace(/([a-zA-Z0-9]+)@zeroid.bit/g, "<a href='?to=$1' onclick='return Page.message_create.show(\"$1\")'>$1@zeroid.bit</a>")

	# Convert zeronet html links to relaitve
	fixHtmlLinks: (text) ->
		if window.is_proxy
			return text.replace(/href="http:\/\/(127.0.0.1|localhost):43110/g, 'href="http://zero')
		else
			return text.replace(/href="http:\/\/(127.0.0.1|localhost):43110/g, 'href="')

	# Convert a single link to relative
	fixLink: (link) ->
		if window.is_proxy
			back = link.replace(/http:\/\/(127.0.0.1|localhost):43110/, 'http://zero')
			return back.replace(/http:\/\/zero\/([^\/]+\.bit)/, "http://$1")  # Domain links
		else
			return link.replace(/http:\/\/(127.0.0.1|localhost):43110/, '')

	toUrl: (text) ->
		return text.replace(/[^A-Za-z0-9]/g, "+").replace(/[+]+/g, "+").replace(/[+]+$/, "")

	getSiteUrl: (address) ->
		if window.is_proxy
			if "." in address # Domain
				return "http://"+address+"/"
			else
				return "http://zero/"+address+"/"
		else
			return "/"+address+"/"


	fixReply: (text) ->
		return text.replace(/(>.*\n)([^\n>])/gm, "$1\n$2")

	toBitcoinAddress: (text) ->
		return text.replace(/[^A-Za-z0-9]/g, "")


	jsonEncode: (obj) ->
		return unescape(encodeURIComponent(JSON.stringify(obj)))

	jsonDecode: (obj) ->
		return JSON.parse(decodeURIComponent(escape(obj)))

	fileEncode: (obj) ->
		if typeof(obj) == "string"
			return btoa(unescape(encodeURIComponent(obj)))
		else
			return btoa(unescape(encodeURIComponent(JSON.stringify(obj, undefined, '\t'))))

	utf8Encode: (s) ->
		return unescape(encodeURIComponent(s))

	utf8Decode: (s) ->
		return decodeURIComponent(escape(s))


	distance: (s1, s2) ->
		s1 = s1.toLocaleLowerCase()
		s2 = s2.toLocaleLowerCase()
		next_find_i = 0
		next_find = s2[0]
		match = true
		extra_parts = {}
		for char in s1
			if char != next_find
				if extra_parts[next_find_i]
					extra_parts[next_find_i] += char
				else
					extra_parts[next_find_i] = char
			else
				next_find_i++
				next_find = s2[next_find_i]

		if extra_parts[next_find_i]
			extra_parts[next_find_i] = ""  # Extra chars on the end doesnt matter
		extra_parts = (val for key, val of extra_parts)
		if next_find_i >= s2.length
			return extra_parts.length + extra_parts.join("").length
		else
			return false


	parseQuery: (query) ->
		params = {}
		parts = query.split('&')
		for part in parts
			[key, val] = part.split("=")
			if val
				params[decodeURIComponent(key)] = decodeURIComponent(val)
			else
				params["url"] = decodeURIComponent(key)
		return params

	encodeQuery: (params) ->
		back = []
		if params.url
			back.push(params.url)
		for key, val of params
			if not val or key == "url"
				continue
			back.push("#{encodeURIComponent(key)}=#{encodeURIComponent(val)}")
		return back.join("&")

	highlight: (text, search) ->
		if not text
			return [""]
		parts = text.split(RegExp(search, "i"))
		back = []
		for part, i in parts
			back.push(part)
			if i < parts.length-1
				back.push(h("span.highlight", {key: i}, search))
		return back

	formatSize: (size) ->
		if isNaN(parseInt(size))
			return ""
		size_mb = size/1024/1024
		if size_mb >= 1000
			return (size_mb/1024).toFixed(1)+" GB"
		else if size_mb >= 100
			return size_mb.toFixed(0)+" MB"
		else if size/1024 >= 1000
			return size_mb.toFixed(2)+" MB"
		else
			return (parseInt(size)/1024).toFixed(2)+" KB"

window.is_proxy = (document.location.host == "zero" or window.location.pathname == "/")
window.Text = new Text()
