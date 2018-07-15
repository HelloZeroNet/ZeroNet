class Animation
	slideDown: (elem, props) ->
		if elem.offsetTop > 2000
			return

		h = elem.offsetHeight
		cstyle = window.getComputedStyle(elem)
		margin_top = cstyle.marginTop
		margin_bottom = cstyle.marginBottom
		padding_top = cstyle.paddingTop
		padding_bottom = cstyle.paddingBottom
		transition = cstyle.transition

		elem.style.boxSizing = "border-box"
		elem.style.overflow = "hidden"
		elem.style.transform = "scale(0.6)"
		elem.style.opacity = "0"
		elem.style.height = "0px"
		elem.style.marginTop = "0px"
		elem.style.marginBottom = "0px"
		elem.style.paddingTop = "0px"
		elem.style.paddingBottom = "0px"
		elem.style.transition = "none"

		setTimeout (->
			elem.className += " animate-inout"
			elem.style.height = h+"px"
			elem.style.transform = "scale(1)"
			elem.style.opacity = "1"
			elem.style.marginTop = margin_top
			elem.style.marginBottom = margin_bottom
			elem.style.paddingTop = padding_top
			elem.style.paddingBottom = padding_bottom
		), 1

		elem.addEventListener "transitionend", ->
			elem.classList.remove("animate-inout")
			elem.style.transition = elem.style.transform = elem.style.opacity = elem.style.height = null
			elem.style.boxSizing = elem.style.marginTop = elem.style.marginBottom = null
			elem.style.paddingTop = elem.style.paddingBottom = elem.style.overflow = null
			elem.removeEventListener "transitionend", arguments.callee, false


	slideUp: (elem, remove_func, props) ->
		if elem.offsetTop > 1000
			return remove_func()

		elem.className += " animate-back"
		elem.style.boxSizing = "border-box"
		elem.style.height = elem.offsetHeight+"px"
		elem.style.overflow = "hidden"
		elem.style.transform = "scale(1)"
		elem.style.opacity = "1"
		elem.style.pointerEvents = "none"
		setTimeout (->
			elem.style.height = "0px"
			elem.style.marginTop = "0px"
			elem.style.marginBottom = "0px"
			elem.style.paddingTop = "0px"
			elem.style.paddingBottom = "0px"
			elem.style.transform = "scale(0.8)"
			elem.style.borderTopWidth = "0px"
			elem.style.borderBottomWidth = "0px"
			elem.style.opacity = "0"
		), 1
		elem.addEventListener "transitionend", (e) ->
			if e.propertyName == "opacity" or e.elapsedTime >= 0.6
				elem.removeEventListener "transitionend", arguments.callee, false
				remove_func()


	slideUpInout: (elem, remove_func, props) ->
		elem.className += " animate-inout"
		elem.style.boxSizing = "border-box"
		elem.style.height = elem.offsetHeight+"px"
		elem.style.overflow = "hidden"
		elem.style.transform = "scale(1)"
		elem.style.opacity = "1"
		elem.style.pointerEvents = "none"
		setTimeout (->
			elem.style.height = "0px"
			elem.style.marginTop = "0px"
			elem.style.marginBottom = "0px"
			elem.style.paddingTop = "0px"
			elem.style.paddingBottom = "0px"
			elem.style.transform = "scale(0.8)"
			elem.style.borderTopWidth = "0px"
			elem.style.borderBottomWidth = "0px"
			elem.style.opacity = "0"
		), 1
		elem.addEventListener "transitionend", (e) ->
			if e.propertyName == "opacity" or e.elapsedTime >= 0.6
				elem.removeEventListener "transitionend", arguments.callee, false
				remove_func()


	showRight: (elem, props) ->
		elem.className += " animate"
		elem.style.opacity = 0
		elem.style.transform = "TranslateX(-20px) Scale(1.01)"
		setTimeout (->
			elem.style.opacity = 1
			elem.style.transform = "TranslateX(0px) Scale(1)"
		), 1
		elem.addEventListener "transitionend", ->
			elem.classList.remove("animate")
			elem.style.transform = elem.style.opacity = null


	show: (elem, props) ->
		delay = arguments[arguments.length-2]?.delay*1000 or 1
		elem.style.opacity = 0
		setTimeout (->
			elem.className += " animate"
		), 1
		setTimeout (->
			elem.style.opacity = 1
		), delay
		elem.addEventListener "transitionend", ->
			elem.classList.remove("animate")
			elem.style.opacity = null
			elem.removeEventListener "transitionend", arguments.callee, false

	hide: (elem, remove_func, props) ->
		delay = arguments[arguments.length-2]?.delay*1000 or 1
		elem.className += " animate"
		setTimeout (->
			elem.style.opacity = 0
		), delay
		elem.addEventListener "transitionend", (e) ->
			if e.propertyName == "opacity"
				remove_func()

	addVisibleClass: (elem, props) ->
		setTimeout ->
			elem.classList.add("visible")

window.Animation = new Animation()