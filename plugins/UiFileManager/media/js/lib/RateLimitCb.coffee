last_time = {}
calling = {}
calling_iterval = {}
call_after_interval = {}

# Rate limit function call and don't allow to run in parallel (until callback is called)
window.RateLimitCb = (interval, fn, args=[]) ->
    cb = ->  # Callback when function finished
        left = interval - (Date.now() - last_time[fn])  # Time life until next call
        # console.log "CB, left", left, "Calling:", calling[fn]
        if left <= 0  # No time left from rate limit interval
            delete last_time[fn]
            if calling[fn]  # Function called within interval
                RateLimitCb(interval, fn, calling[fn])
            delete calling[fn]
        else  # Time left from rate limit interval
            setTimeout (->
                delete last_time[fn]
                if calling[fn]  # Function called within interval
                    RateLimitCb(interval, fn, calling[fn])
                delete calling[fn]
            ), left
    if last_time[fn]  # Function called within interval
        calling[fn] = args  # Schedule call and update arguments
    else  # Not called within interval, call instantly
        last_time[fn] = Date.now()
        fn.apply(this, [cb, args...])


window.RateLimit = (interval, fn) ->
    if calling_iterval[fn] > interval
        clearInterval calling[fn]
        delete calling[fn]

    if not calling[fn]
        call_after_interval[fn] = false
        fn() # First call is not delayed
        calling_iterval[fn] = interval
        calling[fn] = setTimeout (->
            if call_after_interval[fn]
                fn()
            delete calling[fn]
            delete call_after_interval[fn]
        ), interval
    else # Called within iterval, delay the call
        call_after_interval[fn] = true


###
window.s = Date.now()
window.load = (done, num) ->
  console.log "Loading #{num}...", Date.now()-window.s
  setTimeout (-> done()), 1000

RateLimit 500, window.load, [0] # Called instantly
RateLimit 500, window.load, [1]
setTimeout (-> RateLimit 500, window.load, [300]), 300
setTimeout (-> RateLimit 500, window.load, [600]), 600 # Called after 1000ms
setTimeout (-> RateLimit 500, window.load, [1000]), 1000
setTimeout (-> RateLimit 500, window.load, [1200]), 1200  # Called after 2000ms
setTimeout (-> RateLimit 500, window.load, [3000]), 3000  # Called after 3000ms
###