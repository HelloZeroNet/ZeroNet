# From: http://dev.bizo.com/2011/12/promises-in-javascriptcoffeescript.html

class Promise
	@when: (tasks...) ->
		num_uncompleted = tasks.length
		args = new Array(num_uncompleted)
		promise = new Promise()

		for task, task_id in tasks
			((task_id) ->
				task.then(() ->
					args[task_id] = Array.prototype.slice.call(arguments)
					num_uncompleted--
					promise.complete.apply(promise, args) if num_uncompleted == 0
				)
			)(task_id)

		return promise

	constructor: ->
		@resolved = false
		@end_promise = null
		@result = null
		@callbacks = []

	resolve: ->
		if @resolved
			return false
		@resolved = true
		@data = arguments
		if not arguments.length
			@data = [true]
		@result = @data[0]
		for callback in @callbacks
			back = callback.apply callback, @data
		if @end_promise
			@end_promise.resolve(back)

	fail: ->
		@resolve(false)

	then: (callback) ->
		if @resolved == true
			callback.apply callback, @data
			return

		@callbacks.push callback

		@end_promise = new Promise()

window.Promise = Promise

###
s = Date.now()
log = (text) ->
	console.log Date.now()-s, Array.prototype.slice.call(arguments).join(", ")

log "Started"

cmd = (query) ->
	p = new Promise()
	setTimeout ( ->
		p.resolve query+" Result"
	), 100
	return p

back = cmd("SELECT * FROM message").then (res) ->
	log res
	return "Return from query"
.then (res) ->
	log "Back then", res

log "Query started", back
###