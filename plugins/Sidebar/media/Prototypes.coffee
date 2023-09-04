String::startsWith = (s) -> @[...s.length] is s
String::endsWith = (s) -> s is '' or @[-s.length..] is s
String::capitalize = ->  if @.length then @[0].toUpperCase() + @.slice(1) else ""
String::repeat = (count) -> new Array( count + 1 ).join(@)

window.isEmpty = (obj) ->
	for key of obj
		return false
	return true
