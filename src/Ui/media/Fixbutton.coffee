class Fixbutton
	constructor: ->
		@dragging = false
		$(".fixbutton-bg").on "mouseover", ->
			$(".fixbutton-bg").stop().animate({"scale": 0.7}, 800, "easeOutElastic")
			$(".fixbutton-burger").stop().animate({"opacity": 1.5, "left": 0}, 800, "easeOutElastic")
			$(".fixbutton-text").stop().animate({"opacity": 0, "left": 20}, 300, "easeOutCubic")

		$(".fixbutton-bg").on "mouseout", ->
			if $(".fixbutton").hasClass("dragging")
				return true
			$(".fixbutton-bg").stop().animate({"scale": 0.6}, 300, "easeOutCubic")
			$(".fixbutton-burger").stop().animate({"opacity": 0, "left": -20}, 300, "easeOutCubic")
			$(".fixbutton-text").stop().animate({"opacity": 1, "left": 0}, 300, "easeOutBack")


		###$(".fixbutton-bg").on "click", ->
			return false
		###

		$(".fixbutton-bg").on "mousedown", ->
			# $(".fixbutton-burger").stop().animate({"scale": 0.7, "left": 0}, 300, "easeOutCubic")
			#$("#inner-iframe").toggleClass("back")
			#$(".wrapper-iframe").stop().animate({"scale": 0.9}, 600, "easeOutCubic")
			#$("body").addClass("back")

		$(".fixbutton-bg").on "mouseup", ->
			# $(".fixbutton-burger").stop().animate({"scale": 1, "left": 0}, 600, "easeOutElastic")



window.Fixbutton = Fixbutton
