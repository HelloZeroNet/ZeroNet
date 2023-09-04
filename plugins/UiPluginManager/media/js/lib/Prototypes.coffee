String::startsWith = (s) -> @[...s.length] is s
String::endsWith = (s) -> s is '' or @[-s.length..] is s
String::repeat = (count) -> new Array( count + 1 ).join(@)

window.isEmpty = (obj) ->
	for key of obj
		return false
	return true
