class Class
	trace: true

	log: (args...) ->
		return unless @trace
		return if typeof console is 'undefined'
		args.unshift("[#{@.constructor.name}]")
		console.log(args...)
		@
		
	logStart: (name, args...) ->
		return unless @trace
		@logtimers or= {}
		@logtimers[name] = +(new Date)
		@log "#{name}", args..., "(started)" if args.length > 0
		@
		
	logEnd: (name, args...) ->
		ms = +(new Date)-@logtimers[name]
		@log "#{name}", args..., "(Done in #{ms}ms)"
		@ 

window.Class = Class