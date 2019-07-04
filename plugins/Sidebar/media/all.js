
/* ---- plugins/Sidebar/media/Class.coffee ---- */


(function() {
  var Class,
    slice = [].slice;

  Class = (function() {
    function Class() {}

    Class.prototype.trace = true;

    Class.prototype.log = function() {
      var args;
      args = 1 <= arguments.length ? slice.call(arguments, 0) : [];
      if (!this.trace) {
        return;
      }
      if (typeof console === 'undefined') {
        return;
      }
      args.unshift("[" + this.constructor.name + "]");
      console.log.apply(console, args);
      return this;
    };

    Class.prototype.logStart = function() {
      var args, name;
      name = arguments[0], args = 2 <= arguments.length ? slice.call(arguments, 1) : [];
      if (!this.trace) {
        return;
      }
      this.logtimers || (this.logtimers = {});
      this.logtimers[name] = +(new Date);
      if (args.length > 0) {
        this.log.apply(this, ["" + name].concat(slice.call(args), ["(started)"]));
      }
      return this;
    };

    Class.prototype.logEnd = function() {
      var args, ms, name;
      name = arguments[0], args = 2 <= arguments.length ? slice.call(arguments, 1) : [];
      ms = +(new Date) - this.logtimers[name];
      this.log.apply(this, ["" + name].concat(slice.call(args), ["(Done in " + ms + "ms)"]));
      return this;
    };

    return Class;

  })();

  window.Class = Class;

}).call(this);


/* ---- plugins/Sidebar/media/Console.coffee ---- */


(function() {
  var Console,
    bind = function(fn, me){ return function(){ return fn.apply(me, arguments); }; },
    extend = function(child, parent) { for (var key in parent) { if (hasProp.call(parent, key)) child[key] = parent[key]; } function ctor() { this.constructor = child; } ctor.prototype = parent.prototype; child.prototype = new ctor(); child.__super__ = parent.prototype; return child; },
    hasProp = {}.hasOwnProperty;

  Console = (function(superClass) {
    extend(Console, superClass);

    function Console(sidebar) {
      var handleMessageWebsocket_original;
      this.sidebar = sidebar;
      this.stopDragY = bind(this.stopDragY, this);
      this.cleanup = bind(this.cleanup, this);
      this.onClosed = bind(this.onClosed, this);
      this.onOpened = bind(this.onOpened, this);
      this.open = bind(this.open, this);
      this.close = bind(this.close, this);
      this.loadConsoleText = bind(this.loadConsoleText, this);
      this.addLines = bind(this.addLines, this);
      this.formatLine = bind(this.formatLine, this);
      this.checkTextIsBottom = bind(this.checkTextIsBottom, this);
      this.tag = null;
      this.opened = false;
      this.filter = null;
      handleMessageWebsocket_original = this.sidebar.wrapper.handleMessageWebsocket;
      this.sidebar.wrapper.handleMessageWebsocket = (function(_this) {
        return function(message) {
          if (message.cmd === "logLineAdd" && message.params.stream_id === _this.stream_id) {
            return _this.addLines(message.params.lines);
          } else {
            return handleMessageWebsocket_original(message);
          }
        };
      })(this);
      if (window.top.location.hash === "#console") {
        setTimeout(((function(_this) {
          return function() {
            return _this.open();
          };
        })(this)), 10);
      }
    }

    Console.prototype.createHtmltag = function() {
      if (!this.container) {
        this.container = $("<div class=\"console-container\">\n	<div class=\"console\">\n		<div class=\"console-top\">\n			<div class=\"console-text\">Loading...</div>\n		</div>\n		<div class=\"console-middle\">\n			<div class=\"mynode\"></div>\n			<div class=\"peers\">\n				<div class=\"peer\"><div class=\"line\"></div><a href=\"#\" class=\"icon\">\u25BD</div></div>\n			</div>\n		</div>\n	</div>\n</div>");
        this.text = this.container.find(".console-text");
        this.text_elem = this.text[0];
        this.text.on("mousewheel", (function(_this) {
          return function(e) {
            if (e.originalEvent.deltaY < 0) {
              _this.text.stop();
            }
            return RateLimit(300, _this.checkTextIsBottom);
          };
        })(this));
        this.text.is_bottom = true;
        this.container.appendTo(document.body);
        this.tag = this.container.find(".console");
        this.container.on("mousedown touchend touchcancel", (function(_this) {
          return function(e) {
            if (e.target !== e.currentTarget) {
              return true;
            }
            _this.log("closing");
            if ($(document.body).hasClass("body-console")) {
              _this.close();
              return true;
            }
          };
        })(this));
        return this.loadConsoleText();
      }
    };

    Console.prototype.checkTextIsBottom = function() {
      return this.text.is_bottom = Math.round(this.text_elem.scrollTop + this.text_elem.clientHeight) >= this.text_elem.scrollHeight - 15;
    };

    Console.prototype.toColor = function(text, saturation, lightness) {
      var hash, i, j, ref;
      if (saturation == null) {
        saturation = 60;
      }
      if (lightness == null) {
        lightness = 70;
      }
      hash = 0;
      for (i = j = 0, ref = text.length - 1; 0 <= ref ? j <= ref : j >= ref; i = 0 <= ref ? ++j : --j) {
        hash += text.charCodeAt(i) * i;
        hash = hash % 1777;
      }
      return "hsl(" + (hash % 360) + ("," + saturation + "%," + lightness + "%)");
    };

    Console.prototype.formatLine = function(line) {
      var added, level, match, module, ref, text;
      match = line.match(/(\[.*?\])[ ]+(.*?)[ ]+(.*?)[ ]+(.*)/);
      if (!match) {
        return line.replace(/\</g, "&lt;").replace(/\>/g, "&gt;");
      }
      ref = line.match(/(\[.*?\])[ ]+(.*?)[ ]+(.*?)[ ]+(.*)/), line = ref[0], added = ref[1], level = ref[2], module = ref[3], text = ref[4];
      added = "<span style='color: #dfd0fa'>" + added + "</span>";
      level = "<span style='color: " + (this.toColor(level, 100)) + ";'>" + level + "</span>";
      module = "<span style='color: " + (this.toColor(module, 60)) + "; font-weight: bold;'>" + module + "</span>";
      text = text.replace(/(Site:[A-Za-z0-9\.]+)/g, "<span style='color: #AAAAFF'>$1</span>");
      text = text.replace(/\</g, "&lt;").replace(/\>/g, "&gt;");
      return added + " " + level + " " + module + " " + text;
    };

    Console.prototype.addLines = function(lines, animate) {
      var html_lines, j, len, line;
      if (animate == null) {
        animate = true;
      }
      html_lines = [];
      this.logStart("formatting");
      for (j = 0, len = lines.length; j < len; j++) {
        line = lines[j];
        html_lines.push(this.formatLine(line));
      }
      this.logEnd("formatting");
      this.logStart("adding");
      this.text.append(html_lines.join("<br>") + "<br>");
      this.logEnd("adding");
      if (this.text.is_bottom && animate) {
        return this.text.stop().animate({
          scrollTop: this.text_elem.scrollHeight - this.text_elem.clientHeight + 1
        }, 600, 'easeInOutCubic');
      }
    };

    Console.prototype.loadConsoleText = function() {
      this.sidebar.wrapper.ws.cmd("consoleLogRead", {
        filter: this.filter
      }, (function(_this) {
        return function(res) {
          var pos_diff, size_read, size_total;
          _this.text.html("");
          pos_diff = res["pos_end"] - res["pos_start"];
          size_read = Math.round(pos_diff / 1024);
          size_total = Math.round(res['pos_end'] / 1024);
          _this.text.append("Displaying " + res.lines.length + " of " + res.num_found + " lines found in the last " + size_read + "kB of the log file. (" + size_total + "kB total)<br>");
          _this.addLines(res.lines, false);
          return _this.text_elem.scrollTop = _this.text_elem.scrollHeight;
        };
      })(this));
      return this.sidebar.wrapper.ws.cmd("consoleLogStream", {
        filter: this.filter
      }, (function(_this) {
        return function(res) {
          return _this.stream_id = res.stream_id;
        };
      })(this));
    };

    Console.prototype.close = function() {
      this.sidebar.move_lock = "y";
      this.sidebar.startDrag();
      return this.sidebar.stopDrag();
    };

    Console.prototype.open = function() {
      this.createHtmltag();
      this.sidebar.fixbutton_targety = this.sidebar.page_height;
      return this.stopDragY();
    };

    Console.prototype.onOpened = function() {
      this.sidebar.onClosed();
      return this.log("onOpened");
    };

    Console.prototype.onClosed = function() {
      $(document.body).removeClass("body-console");
      if (this.stream_id) {
        return this.sidebar.wrapper.ws.cmd("consoleLogStreamRemove", {
          stream_id: this.stream_id
        });
      }
    };

    Console.prototype.cleanup = function() {
      if (this.container) {
        this.container.remove();
        return this.container = null;
      }
    };

    Console.prototype.stopDragY = function() {
      var targety;
      if (this.sidebar.fixbutton_targety === this.sidebar.fixbutton_inity) {
        targety = 0;
        this.opened = false;
      } else {
        targety = this.sidebar.fixbutton_targety - this.sidebar.fixbutton_inity;
        this.onOpened();
        this.opened = true;
      }
      if (this.tag) {
        this.tag.css("transition", "0.5s ease-out");
        this.tag.css("transform", "translateY(" + targety + "px)").one(transitionEnd, (function(_this) {
          return function() {
            _this.tag.css("transition", "");
            if (!_this.opened) {
              return _this.cleanup();
            }
          };
        })(this));
      }
      this.log("stopDragY", "opened:", this.opened, targety);
      if (!this.opened) {
        return this.onClosed();
      }
    };

    return Console;

  })(Class);

  window.Console = Console;

}).call(this);


/* ---- plugins/Sidebar/media/Menu.coffee ---- */


(function() {
  var Menu,
    slice = [].slice;

  Menu = (function() {
    function Menu(button) {
      this.button = button;
      this.elem = $(".menu.template").clone().removeClass("template");
      this.elem.appendTo("body");
      this.items = [];
    }

    Menu.prototype.show = function() {
      var button_pos, left;
      if (window.visible_menu && window.visible_menu.button[0] === this.button[0]) {
        window.visible_menu.hide();
        return this.hide();
      } else {
        button_pos = this.button.offset();
        left = button_pos.left;
        this.elem.css({
          "top": button_pos.top + this.button.outerHeight(),
          "left": left
        });
        this.button.addClass("menu-active");
        this.elem.addClass("visible");
        if (this.elem.position().left + this.elem.width() + 20 > window.innerWidth) {
          this.elem.css("left", window.innerWidth - this.elem.width() - 20);
        }
        if (window.visible_menu) {
          window.visible_menu.hide();
        }
        return window.visible_menu = this;
      }
    };

    Menu.prototype.hide = function() {
      this.elem.removeClass("visible");
      this.button.removeClass("menu-active");
      return window.visible_menu = null;
    };

    Menu.prototype.addItem = function(title, cb) {
      var item;
      item = $(".menu-item.template", this.elem).clone().removeClass("template");
      item.html(title);
      item.on("click", (function(_this) {
        return function() {
          if (!cb(item)) {
            _this.hide();
          }
          return false;
        };
      })(this));
      item.appendTo(this.elem);
      this.items.push(item);
      return item;
    };

    Menu.prototype.log = function() {
      var args;
      args = 1 <= arguments.length ? slice.call(arguments, 0) : [];
      return console.log.apply(console, ["[Menu]"].concat(slice.call(args)));
    };

    return Menu;

  })();

  window.Menu = Menu;

  $("body").on("click", function(e) {
    if (window.visible_menu && e.target !== window.visible_menu.button[0] && $(e.target).parent()[0] !== window.visible_menu.elem[0]) {
      return window.visible_menu.hide();
    }
  });

}).call(this);


/* ---- plugins/Sidebar/media/RateLimit.coffee ---- */


(function() {
  var call_after_interval, limits;

  limits = {};

  call_after_interval = {};

  window.RateLimit = function(interval, fn) {
    if (!limits[fn]) {
      call_after_interval[fn] = false;
      fn();
      return limits[fn] = setTimeout((function() {
        if (call_after_interval[fn]) {
          fn();
        }
        delete limits[fn];
        return delete call_after_interval[fn];
      }), interval);
    } else {
      return call_after_interval[fn] = true;
    }
  };

}).call(this);


/* ---- plugins/Sidebar/media/Scrollable.js ---- */


/* via http://jsfiddle.net/elGrecode/00dgurnn/ */

window.initScrollable = function () {

    var scrollContainer = document.querySelector('.scrollable'),
        scrollContentWrapper = document.querySelector('.scrollable .content-wrapper'),
        scrollContent = document.querySelector('.scrollable .content'),
        contentPosition = 0,
        scrollerBeingDragged = false,
        scroller,
        topPosition,
        scrollerHeight;

    function calculateScrollerHeight() {
        // *Calculation of how tall scroller should be
        var visibleRatio = scrollContainer.offsetHeight / scrollContentWrapper.scrollHeight;
        if (visibleRatio == 1)
            scroller.style.display = "none";
        else
            scroller.style.display = "block";
        return visibleRatio * scrollContainer.offsetHeight;
    }

    function moveScroller(evt) {
        // Move Scroll bar to top offset
        var scrollPercentage = evt.target.scrollTop / scrollContentWrapper.scrollHeight;
        topPosition = scrollPercentage * (scrollContainer.offsetHeight - 5); // 5px arbitrary offset so scroll bar doesn't move too far beyond content wrapper bounding box
        scroller.style.top = topPosition + 'px';
    }

    function startDrag(evt) {
        normalizedPosition = evt.pageY;
        contentPosition = scrollContentWrapper.scrollTop;
        scrollerBeingDragged = true;
        window.addEventListener('mousemove', scrollBarScroll);
        return false;
    }

    function stopDrag(evt) {
        scrollerBeingDragged = false;
        window.removeEventListener('mousemove', scrollBarScroll);
    }

    function scrollBarScroll(evt) {
        if (scrollerBeingDragged === true) {
            evt.preventDefault();
            var mouseDifferential = evt.pageY - normalizedPosition;
            var scrollEquivalent = mouseDifferential * (scrollContentWrapper.scrollHeight / scrollContainer.offsetHeight);
            scrollContentWrapper.scrollTop = contentPosition + scrollEquivalent;
        }
    }

    function updateHeight() {
        scrollerHeight = calculateScrollerHeight() - 10;
        scroller.style.height = scrollerHeight + 'px';
    }

    function createScroller() {
        // *Creates scroller element and appends to '.scrollable' div
        // create scroller element
        scroller = document.createElement("div");
        scroller.className = 'scroller';

        // determine how big scroller should be based on content
        scrollerHeight = calculateScrollerHeight() - 10;

        if (scrollerHeight / scrollContainer.offsetHeight < 1) {
            // *If there is a need to have scroll bar based on content size
            scroller.style.height = scrollerHeight + 'px';

            // append scroller to scrollContainer div
            scrollContainer.appendChild(scroller);

            // show scroll path divot
            scrollContainer.className += ' showScroll';

            // attach related draggable listeners
            scroller.addEventListener('mousedown', startDrag);
            window.addEventListener('mouseup', stopDrag);
        }

    }

    createScroller();


    // *** Listeners ***
    scrollContentWrapper.addEventListener('scroll', moveScroller);

    return updateHeight;
};

/* ---- plugins/Sidebar/media/Sidebar.coffee ---- */


(function() {
  var Sidebar, wrapper,
    bind = function(fn, me){ return function(){ return fn.apply(me, arguments); }; },
    extend = function(child, parent) { for (var key in parent) { if (hasProp.call(parent, key)) child[key] = parent[key]; } function ctor() { this.constructor = child; } ctor.prototype = parent.prototype; child.prototype = new ctor(); child.__super__ = parent.prototype; return child; },
    hasProp = {}.hasOwnProperty,
    indexOf = [].indexOf || function(item) { for (var i = 0, l = this.length; i < l; i++) { if (i in this && this[i] === item) return i; } return -1; };

  Sidebar = (function(superClass) {
    extend(Sidebar, superClass);

    function Sidebar(wrapper1) {
      this.wrapper = wrapper1;
      this.unloadGlobe = bind(this.unloadGlobe, this);
      this.displayGlobe = bind(this.displayGlobe, this);
      this.loadGlobe = bind(this.loadGlobe, this);
      this.animDrag = bind(this.animDrag, this);
      this.setHtmlTag = bind(this.setHtmlTag, this);
      this.waitMove = bind(this.waitMove, this);
      this.resized = bind(this.resized, this);
      this.tag = null;
      this.container = null;
      this.opened = false;
      this.width = 410;
      this.console = new Console(this);
      this.fixbutton = $(".fixbutton");
      this.fixbutton_addx = 0;
      this.fixbutton_addy = 0;
      this.fixbutton_initx = 0;
      this.fixbutton_inity = 15;
      this.fixbutton_targetx = 0;
      this.move_lock = null;
      this.page_width = $(window).width();
      this.page_height = $(window).height();
      this.frame = $("#inner-iframe");
      this.initFixbutton();
      this.dragStarted = 0;
      this.globe = null;
      this.preload_html = null;
      this.original_set_site_info = this.wrapper.setSiteInfo;
      if (false) {
        this.startDrag();
        this.moved();
        this.fixbutton_targetx = this.fixbutton_initx - this.width;
        this.stopDrag();
      }
    }

    Sidebar.prototype.initFixbutton = function() {
      this.fixbutton.on("mousedown touchstart", (function(_this) {
        return function(e) {
          if (e.button > 0) {
            return;
          }
          e.preventDefault();
          _this.fixbutton.off("click touchend touchcancel");
          _this.dragStarted = +(new Date);
          $(".drag-bg").remove();
          $("<div class='drag-bg'></div>").appendTo(document.body);
          return $("body").one("mousemove touchmove", function(e) {
            var mousex, mousey;
            mousex = e.pageX;
            mousey = e.pageY;
            if (!mousex) {
              mousex = e.originalEvent.touches[0].pageX;
              mousey = e.originalEvent.touches[0].pageY;
            }
            _this.fixbutton_addx = _this.fixbutton.offset().left - mousex;
            _this.fixbutton_addy = _this.fixbutton.offset().top - mousey;
            return _this.startDrag();
          });
        };
      })(this));
      this.fixbutton.parent().on("click touchend touchcancel", (function(_this) {
        return function(e) {
          if ((+(new Date)) - _this.dragStarted < 100) {
            window.top.location = _this.fixbutton.find(".fixbutton-bg").attr("href");
          }
          return _this.stopDrag();
        };
      })(this));
      this.resized();
      return $(window).on("resize", this.resized);
    };

    Sidebar.prototype.resized = function() {
      this.page_width = $(window).width();
      this.page_height = $(window).height();
      this.fixbutton_initx = this.page_width - 75;
      if (this.opened) {
        return this.fixbutton.css({
          left: this.fixbutton_initx - this.width
        });
      } else {
        return this.fixbutton.css({
          left: this.fixbutton_initx
        });
      }
    };

    Sidebar.prototype.startDrag = function() {
      this.log("startDrag", this.fixbutton_initx, this.fixbutton_inity);
      this.fixbutton_targetx = this.fixbutton_initx;
      this.fixbutton_targety = this.fixbutton_inity;
      this.fixbutton.addClass("dragging");
      if (navigator.userAgent.indexOf('MSIE') !== -1 || navigator.appVersion.indexOf('Trident/') > 0) {
        this.fixbutton.css("pointer-events", "none");
      }
      this.fixbutton.one("click", (function(_this) {
        return function(e) {
          var moved_x, moved_y;
          _this.stopDrag();
          _this.fixbutton.removeClass("dragging");
          moved_x = Math.abs(_this.fixbutton.offset().left - _this.fixbutton_initx);
          moved_y = Math.abs(_this.fixbutton.offset().top - _this.fixbutton_inity);
          if (moved_x > 5 || moved_y > 10) {
            return e.preventDefault();
          }
        };
      })(this));
      this.fixbutton.parents().on("mousemove touchmove", this.animDrag);
      this.fixbutton.parents().on("mousemove touchmove", this.waitMove);
      return this.fixbutton.parents().one("mouseup touchend touchcancel", (function(_this) {
        return function(e) {
          e.preventDefault();
          return _this.stopDrag();
        };
      })(this));
    };

    Sidebar.prototype.waitMove = function(e) {
      var moved_x, moved_y;
      document.body.style.perspective = "1000px";
      document.body.style.height = "100%";
      document.body.style.willChange = "perspective";
      document.documentElement.style.height = "100%";
      moved_x = Math.abs(parseInt(this.fixbutton[0].style.left) - this.fixbutton_targetx);
      moved_y = Math.abs(parseInt(this.fixbutton[0].style.top) - this.fixbutton_targety);
      if (moved_x > 5 && (+(new Date)) - this.dragStarted + moved_x > 50) {
        this.moved("x");
        this.fixbutton.stop().animate({
          "top": this.fixbutton_inity
        }, 1000);
        return this.fixbutton.parents().off("mousemove touchmove", this.waitMove);
      } else if (moved_y > 5 && (+(new Date)) - this.dragStarted + moved_y > 50) {
        this.moved("y");
        return this.fixbutton.parents().off("mousemove touchmove", this.waitMove);
      }
    };

    Sidebar.prototype.moved = function(direction) {
      var img;
      this.log("Moved", direction);
      this.move_lock = direction;
      if (direction === "y") {
        $(document.body).addClass("body-console");
        return this.console.createHtmltag();
      }
      this.createHtmltag();
      $(document.body).addClass("body-sidebar");
      this.container.on("mousedown touchend touchcancel", (function(_this) {
        return function(e) {
          if (e.target !== e.currentTarget) {
            return true;
          }
          _this.log("closing");
          if ($(document.body).hasClass("body-sidebar")) {
            _this.close();
            return true;
          }
        };
      })(this));
      $(window).off("resize");
      $(window).on("resize", (function(_this) {
        return function() {
          $(document.body).css("height", $(window).height());
          _this.scrollable();
          return _this.resized();
        };
      })(this));
      this.wrapper.setSiteInfo = (function(_this) {
        return function(site_info) {
          _this.setSiteInfo(site_info);
          return _this.original_set_site_info.apply(_this.wrapper, arguments);
        };
      })(this);
      img = new Image();
      return img.src = "/uimedia/globe/world.jpg";
    };

    Sidebar.prototype.setSiteInfo = function(site_info) {
      RateLimit(1500, (function(_this) {
        return function() {
          return _this.updateHtmlTag();
        };
      })(this));
      return RateLimit(30000, (function(_this) {
        return function() {
          return _this.displayGlobe();
        };
      })(this));
    };

    Sidebar.prototype.createHtmltag = function() {
      this.when_loaded = $.Deferred();
      if (!this.container) {
        this.container = $("<div class=\"sidebar-container\"><div class=\"sidebar scrollable\"><div class=\"content-wrapper\"><div class=\"content\">\n</div></div></div></div>");
        this.container.appendTo(document.body);
        this.tag = this.container.find(".sidebar");
        this.updateHtmlTag();
        return this.scrollable = window.initScrollable();
      }
    };

    Sidebar.prototype.updateHtmlTag = function() {
      if (this.preload_html) {
        this.setHtmlTag(this.preload_html);
        return this.preload_html = null;
      } else {
        return this.wrapper.ws.cmd("sidebarGetHtmlTag", {}, this.setHtmlTag);
      }
    };

    Sidebar.prototype.setHtmlTag = function(res) {
      if (this.tag.find(".content").children().length === 0) {
        this.log("Creating content");
        this.container.addClass("loaded");
        morphdom(this.tag.find(".content")[0], '<div class="content">' + res + '</div>');
        this.when_loaded.resolve();
      } else {
        morphdom(this.tag.find(".content")[0], '<div class="content">' + res + '</div>', {
          onBeforeMorphEl: function(from_el, to_el) {
            if (from_el.className === "globe" || from_el.className.indexOf("noupdate") >= 0) {
              return false;
            } else {
              return true;
            }
          }
        });
      }
      this.tag.find("#privatekey-add").off("click, touchend").on("click touchend", (function(_this) {
        return function(e) {
          _this.wrapper.displayPrompt("Enter your private key:", "password", "Save", "", function(privatekey) {
            return _this.wrapper.ws.cmd("userSetSitePrivatekey", [privatekey], function(res) {
              return _this.wrapper.notifications.add("privatekey", "done", "Private key saved for site signing", 5000);
            });
          });
          return false;
        };
      })(this));
      return this.tag.find("#privatekey-forgot").off("click, touchend").on("click touchend", (function(_this) {
        return function(e) {
          _this.wrapper.displayConfirm("Remove saved private key for this site?", "Forgot", function(res) {
            if (!res) {
              return false;
            }
            return _this.wrapper.ws.cmd("userSetSitePrivatekey", [""], function(res) {
              return _this.wrapper.notifications.add("privatekey", "done", "Saved private key removed", 5000);
            });
          });
          return false;
        };
      })(this));
    };

    Sidebar.prototype.animDrag = function(e) {
      var mousex, mousey, overdrag, overdrag_percent, targetx, targety;
      mousex = e.pageX;
      mousey = e.pageY;
      if (!mousex && e.originalEvent.touches) {
        mousex = e.originalEvent.touches[0].pageX;
        mousey = e.originalEvent.touches[0].pageY;
      }
      overdrag = this.fixbutton_initx - this.width - mousex;
      if (overdrag > 0) {
        overdrag_percent = 1 + overdrag / 300;
        mousex = (mousex + (this.fixbutton_initx - this.width) * overdrag_percent) / (1 + overdrag_percent);
      }
      targetx = this.fixbutton_initx - mousex - this.fixbutton_addx;
      targety = this.fixbutton_inity - mousey - this.fixbutton_addy;
      if (this.move_lock === "x") {
        targety = this.fixbutton_inity;
      } else if (this.move_lock === "y") {
        targetx = this.fixbutton_initx;
      }
      if (!this.move_lock || this.move_lock === "x") {
        this.fixbutton[0].style.left = (mousex + this.fixbutton_addx) + "px";
        if (this.tag) {
          this.tag[0].style.transform = "translateX(" + (0 - targetx) + "px)";
        }
      }
      if (!this.move_lock || this.move_lock === "y") {
        this.fixbutton[0].style.top = (mousey + this.fixbutton_addy) + "px";
        if (this.console.tag) {
          this.console.tag[0].style.transform = "translateY(" + (0 - targety) + "px)";
        }
      }
      if ((!this.opened && targetx > this.width / 3) || (this.opened && targetx > this.width * 0.9)) {
        this.fixbutton_targetx = this.fixbutton_initx - this.width;
      } else {
        this.fixbutton_targetx = this.fixbutton_initx;
      }
      if ((!this.console.opened && 0 - targety > this.page_height / 10) || (this.console.opened && 0 - targety > this.page_height * 0.8)) {
        return this.fixbutton_targety = this.page_height - this.fixbutton_inity - 50;
      } else {
        return this.fixbutton_targety = this.fixbutton_inity;
      }
    };

    Sidebar.prototype.stopDrag = function() {
      var left, top;
      this.fixbutton.parents().off("mousemove touchmove");
      this.fixbutton.off("mousemove touchmove");
      this.fixbutton.css("pointer-events", "");
      $(".drag-bg").remove();
      if (!this.fixbutton.hasClass("dragging")) {
        return;
      }
      this.fixbutton.removeClass("dragging");
      if (this.fixbutton_targetx !== this.fixbutton.offset().left || this.fixbutton_targety !== this.fixbutton.offset().top) {
        if (this.move_lock === "y") {
          top = this.fixbutton_targety;
          left = this.fixbutton_initx;
        }
        if (this.move_lock === "x") {
          top = this.fixbutton_inity;
          left = this.fixbutton_targetx;
        }
        this.fixbutton.stop().animate({
          "left": left,
          "top": top
        }, 500, "easeOutBack", (function(_this) {
          return function() {
            if (_this.fixbutton_targetx === _this.fixbutton_initx) {
              _this.fixbutton.css("left", "auto");
            } else {
              _this.fixbutton.css("left", left);
            }
            return $(".fixbutton-bg").trigger("mouseout");
          };
        })(this));
        this.stopDragX();
        this.console.stopDragY();
      }
      return this.move_lock = null;
    };

    Sidebar.prototype.stopDragX = function() {
      var targetx;
      if (this.fixbutton_targetx === this.fixbutton_initx || this.move_lock === "y") {
        targetx = 0;
        this.opened = false;
      } else {
        targetx = this.width;
        if (this.opened) {
          this.onOpened();
        } else {
          this.when_loaded.done((function(_this) {
            return function() {
              return _this.onOpened();
            };
          })(this));
        }
        this.opened = true;
      }
      if (this.tag) {
        this.tag.css("transition", "0.4s ease-out");
        this.tag.css("transform", "translateX(-" + targetx + "px)").one(transitionEnd, (function(_this) {
          return function() {
            _this.tag.css("transition", "");
            if (!_this.opened) {
              _this.container.remove();
              _this.container = null;
              if (_this.tag) {
                _this.tag.remove();
                return _this.tag = null;
              }
            }
          };
        })(this));
      }
      this.log("stopdrag", "opened:", this.opened);
      if (!this.opened) {
        return this.onClosed();
      }
    };

    Sidebar.prototype.sign = function(inner_path, privatekey) {
      this.wrapper.displayProgress("sign", "Signing: " + inner_path + "...", 0);
      return this.wrapper.ws.cmd("siteSign", {
        privatekey: privatekey,
        inner_path: inner_path,
        update_changed_files: true
      }, (function(_this) {
        return function(res) {
          if (res === "ok") {
            return _this.wrapper.displayProgress("sign", inner_path + " signed!", 100);
          } else {
            return _this.wrapper.displayProgress("sign", "Error signing " + inner_path, -1);
          }
        };
      })(this));
    };

    Sidebar.prototype.publish = function(inner_path, privatekey) {
      return this.wrapper.ws.cmd("sitePublish", {
        privatekey: privatekey,
        inner_path: inner_path,
        sign: true,
        update_changed_files: true
      }, (function(_this) {
        return function(res) {
          if (res === "ok") {
            return _this.wrapper.notifications.add("sign", "done", inner_path + " Signed and published!", 5000);
          }
        };
      })(this));
    };

    Sidebar.prototype.onOpened = function() {
      var menu;
      this.log("Opened");
      this.scrollable();
      this.tag.find("#checkbox-owned, #checkbox-autodownloadoptional").off("click touchend").on("click touchend", (function(_this) {
        return function() {
          return setTimeout((function() {
            return _this.scrollable();
          }), 300);
        };
      })(this));
      this.tag.find("#button-sitelimit").off("click touchend").on("click touchend", (function(_this) {
        return function() {
          _this.wrapper.ws.cmd("siteSetLimit", $("#input-sitelimit").val(), function(res) {
            if (res === "ok") {
              _this.wrapper.notifications.add("done-sitelimit", "done", "Site storage limit modified!", 5000);
            }
            return _this.updateHtmlTag();
          });
          return false;
        };
      })(this));
      this.tag.find("#button-autodownload_bigfile_size_limit").off("click touchend").on("click touchend", (function(_this) {
        return function() {
          _this.wrapper.ws.cmd("siteSetAutodownloadBigfileLimit", $("#input-autodownload_bigfile_size_limit").val(), function(res) {
            if (res === "ok") {
              _this.wrapper.notifications.add("done-bigfilelimit", "done", "Site bigfile auto download limit modified!", 5000);
            }
            return _this.updateHtmlTag();
          });
          return false;
        };
      })(this));
      this.tag.find("#button-dbreload").off("click touchend").on("click touchend", (function(_this) {
        return function() {
          _this.wrapper.ws.cmd("dbReload", [], function() {
            _this.wrapper.notifications.add("done-dbreload", "done", "Database schema reloaded!", 5000);
            return _this.updateHtmlTag();
          });
          return false;
        };
      })(this));
      this.tag.find("#button-dbrebuild").off("click touchend").on("click touchend", (function(_this) {
        return function() {
          _this.wrapper.notifications.add("done-dbrebuild", "info", "Database rebuilding....");
          _this.wrapper.ws.cmd("dbRebuild", [], function() {
            _this.wrapper.notifications.add("done-dbrebuild", "done", "Database rebuilt!", 5000);
            return _this.updateHtmlTag();
          });
          return false;
        };
      })(this));
      this.tag.find("#button-update").off("click touchend").on("click touchend", (function(_this) {
        return function() {
          _this.tag.find("#button-update").addClass("loading");
          _this.wrapper.ws.cmd("siteUpdate", _this.wrapper.site_info.address, function() {
            _this.wrapper.notifications.add("done-updated", "done", "Site updated!", 5000);
            return _this.tag.find("#button-update").removeClass("loading");
          });
          return false;
        };
      })(this));
      this.tag.find("#button-pause").off("click touchend").on("click touchend", (function(_this) {
        return function() {
          _this.tag.find("#button-pause").addClass("hidden");
          _this.wrapper.ws.cmd("sitePause", _this.wrapper.site_info.address);
          return false;
        };
      })(this));
      this.tag.find("#button-resume").off("click touchend").on("click touchend", (function(_this) {
        return function() {
          _this.tag.find("#button-resume").addClass("hidden");
          _this.wrapper.ws.cmd("siteResume", _this.wrapper.site_info.address);
          return false;
        };
      })(this));
      this.tag.find("#button-delete").off("click touchend").on("click touchend", (function(_this) {
        return function() {
          _this.wrapper.displayConfirm("Are you sure?", ["Delete this site", "Blacklist"], function(confirmed) {
            if (confirmed === 1) {
              _this.tag.find("#button-delete").addClass("loading");
              return _this.wrapper.ws.cmd("siteDelete", _this.wrapper.site_info.address, function() {
                return document.location = $(".fixbutton-bg").attr("href");
              });
            } else if (confirmed === 2) {
              return _this.wrapper.displayPrompt("Blacklist this site", "text", "Delete and Blacklist", "Reason", function(reason) {
                _this.tag.find("#button-delete").addClass("loading");
                _this.wrapper.ws.cmd("siteblockAdd", [_this.wrapper.site_info.address, reason]);
                return _this.wrapper.ws.cmd("siteDelete", _this.wrapper.site_info.address, function() {
                  return document.location = $(".fixbutton-bg").attr("href");
                });
              });
            }
          });
          return false;
        };
      })(this));
      this.tag.find("#checkbox-owned").off("click touchend").on("click touchend", (function(_this) {
        return function() {
          return _this.wrapper.ws.cmd("siteSetOwned", [_this.tag.find("#checkbox-owned").is(":checked")]);
        };
      })(this));
      this.tag.find("#checkbox-autodownloadoptional").off("click touchend").on("click touchend", (function(_this) {
        return function() {
          return _this.wrapper.ws.cmd("siteSetAutodownloadoptional", [_this.tag.find("#checkbox-autodownloadoptional").is(":checked")]);
        };
      })(this));
      this.tag.find("#button-identity").off("click touchend").on("click touchend", (function(_this) {
        return function() {
          _this.wrapper.ws.cmd("certSelect");
          return false;
        };
      })(this));
      this.tag.find("#button-settings").off("click touchend").on("click touchend", (function(_this) {
        return function() {
          _this.wrapper.ws.cmd("fileGet", "content.json", function(res) {
            var data, json_raw;
            data = JSON.parse(res);
            data["title"] = $("#settings-title").val();
            data["description"] = $("#settings-description").val();
            json_raw = unescape(encodeURIComponent(JSON.stringify(data, void 0, '\t')));
            return _this.wrapper.ws.cmd("fileWrite", ["content.json", btoa(json_raw), true], function(res) {
              if (res !== "ok") {
                return _this.wrapper.notifications.add("file-write", "error", "File write error: " + res);
              } else {
                _this.wrapper.notifications.add("file-write", "done", "Site settings saved!", 5000);
                if (_this.wrapper.site_info.privatekey) {
                  _this.wrapper.ws.cmd("siteSign", {
                    privatekey: "stored",
                    inner_path: "content.json",
                    update_changed_files: true
                  });
                }
                return _this.updateHtmlTag();
              }
            });
          });
          return false;
        };
      })(this));
      this.tag.find("#link-directory").off("click touchend").on("click touchend", (function(_this) {
        return function() {
          _this.wrapper.ws.cmd("serverShowdirectory", ["site", _this.wrapper.site_info.address]);
          return false;
        };
      })(this));
      this.tag.find("#link-copypeers").off("click touchend").on("click touchend", (function(_this) {
        return function(e) {
          var copy_text, handler;
          copy_text = e.currentTarget.href;
          handler = function(e) {
            e.clipboardData.setData('text/plain', copy_text);
            e.preventDefault();
            _this.wrapper.notifications.add("copy", "done", "Site address with peers copied to your clipboard", 5000);
            return document.removeEventListener('copy', handler, true);
          };
          document.addEventListener('copy', handler, true);
          document.execCommand('copy');
          return false;
        };
      })(this));
      $(document).on("click touchend", (function(_this) {
        return function() {
          var ref, ref1;
          if ((ref = _this.tag) != null) {
            ref.find("#button-sign-publish-menu").removeClass("visible");
          }
          return (ref1 = _this.tag) != null ? ref1.find(".contents + .flex").removeClass("sign-publish-flex") : void 0;
        };
      })(this));
      this.tag.find(".contents-content").off("click touchend").on("click touchend", (function(_this) {
        return function(e) {
          $("#input-contents").val(e.currentTarget.innerText);
          return false;
        };
      })(this));
      menu = new Menu(this.tag.find("#menu-sign-publish"));
      menu.elem.css("margin-top", "-130px");
      menu.addItem("Sign", (function(_this) {
        return function() {
          var inner_path;
          inner_path = _this.tag.find("#input-contents").val();
          _this.wrapper.ws.cmd("fileRules", {
            inner_path: inner_path
          }, function(rules) {
            var ref;
            if (ref = _this.wrapper.site_info.auth_address, indexOf.call(rules.signers, ref) >= 0) {
              return _this.sign(inner_path);
            } else if (_this.wrapper.site_info.privatekey) {
              return _this.sign(inner_path, "stored");
            } else {
              return _this.wrapper.displayPrompt("Enter your private key:", "password", "Sign", "", function(privatekey) {
                return _this.sign(inner_path, privatekey);
              });
            }
          });
          _this.tag.find(".contents + .flex").removeClass("active");
          return menu.hide();
        };
      })(this));
      menu.addItem("Publish", (function(_this) {
        return function() {
          var inner_path;
          inner_path = _this.tag.find("#input-contents").val();
          _this.wrapper.ws.cmd("sitePublish", {
            "inner_path": inner_path,
            "sign": false
          });
          _this.tag.find(".contents + .flex").removeClass("active");
          return menu.hide();
        };
      })(this));
      this.tag.find("#menu-sign-publish").off("click touchend").on("click touchend", (function(_this) {
        return function() {
          if (window.visible_menu === menu) {
            _this.tag.find(".contents + .flex").removeClass("active");
            menu.hide();
          } else {
            _this.tag.find(".contents + .flex").addClass("active");
            _this.tag.find(".content-wrapper").prop("scrollTop", 10000);
            menu.show();
          }
          return false;
        };
      })(this));
      $("body").on("click", (function(_this) {
        return function() {
          if (_this.tag) {
            return _this.tag.find(".contents + .flex").removeClass("active");
          }
        };
      })(this));
      this.tag.find("#button-sign-publish").off("click touchend").on("click touchend", (function(_this) {
        return function() {
          var inner_path;
          inner_path = _this.tag.find("#input-contents").val();
          _this.wrapper.ws.cmd("fileRules", {
            inner_path: inner_path
          }, function(rules) {
            var ref;
            if (ref = _this.wrapper.site_info.auth_address, indexOf.call(rules.signers, ref) >= 0) {
              return _this.publish(inner_path, null);
            } else if (_this.wrapper.site_info.privatekey) {
              return _this.publish(inner_path, "stored");
            } else {
              return _this.wrapper.displayPrompt("Enter your private key:", "password", "Sign", "", function(privatekey) {
                return _this.publish(inner_path, privatekey);
              });
            }
          });
          return false;
        };
      })(this));
      this.tag.find(".close").off("click touchend").on("click touchend", (function(_this) {
        return function(e) {
          _this.close();
          return false;
        };
      })(this));
      return this.loadGlobe();
    };

    Sidebar.prototype.close = function() {
      this.move_lock = "x";
      this.startDrag();
      return this.stopDrag();
    };

    Sidebar.prototype.onClosed = function() {
      $(window).off("resize");
      $(window).on("resize", this.resized);
      $(document.body).css("transition", "0.6s ease-in-out").removeClass("body-sidebar").on(transitionEnd, (function(_this) {
        return function(e) {
          if (e.target === document.body && !$(document.body).hasClass("body-sidebar") && !$(document.body).hasClass("body-console")) {
            $(document.body).css("height", "auto").css("perspective", "").css("will-change", "").css("transition", "").off(transitionEnd);
            return _this.unloadGlobe();
          }
        };
      })(this));
      return this.wrapper.setSiteInfo = this.original_set_site_info;
    };

    Sidebar.prototype.loadGlobe = function() {
      if (this.tag.find(".globe").hasClass("loading")) {
        return setTimeout(((function(_this) {
          return function() {
            var script_tag;
            if (typeof DAT === "undefined") {
              script_tag = $("<script>");
              script_tag.attr("nonce", _this.wrapper.script_nonce);
              script_tag.attr("src", "/uimedia/globe/all.js");
              script_tag.on("load", _this.displayGlobe);
              return document.head.appendChild(script_tag[0]);
            } else {
              return _this.displayGlobe();
            }
          };
        })(this)), 600);
      }
    };

    Sidebar.prototype.displayGlobe = function() {
      var img;
      img = new Image();
      img.src = "/uimedia/globe/world.jpg";
      return img.onload = (function(_this) {
        return function() {
          return _this.wrapper.ws.cmd("sidebarGetPeers", [], function(globe_data) {
            var e, ref, ref1, ref2;
            if (_this.globe) {
              _this.globe.scene.remove(_this.globe.points);
              _this.globe.addData(globe_data, {
                format: 'magnitude',
                name: "hello",
                animated: false
              });
              _this.globe.createPoints();
              return (ref = _this.tag) != null ? ref.find(".globe").removeClass("loading") : void 0;
            } else if (typeof DAT !== "undefined") {
              try {
                _this.globe = new DAT.Globe(_this.tag.find(".globe")[0], {
                  "imgDir": "/uimedia/globe/"
                });
                _this.globe.addData(globe_data, {
                  format: 'magnitude',
                  name: "hello"
                });
                _this.globe.createPoints();
                _this.globe.animate();
              } catch (error) {
                e = error;
                console.log("WebGL error", e);
                if ((ref1 = _this.tag) != null) {
                  ref1.find(".globe").addClass("error").text("WebGL not supported");
                }
              }
              return (ref2 = _this.tag) != null ? ref2.find(".globe").removeClass("loading") : void 0;
            }
          });
        };
      })(this);
    };

    Sidebar.prototype.unloadGlobe = function() {
      if (!this.globe) {
        return false;
      }
      this.globe.unload();
      return this.globe = null;
    };

    return Sidebar;

  })(Class);

  wrapper = window.wrapper;

  setTimeout((function() {
    return window.sidebar = new Sidebar(wrapper);
  }), 500);

  window.transitionEnd = 'transitionend webkitTransitionEnd oTransitionEnd otransitionend';

}).call(this);


/* ---- plugins/Sidebar/media/morphdom.js ---- */


(function(f){if(typeof exports==="object"&&typeof module!=="undefined"){module.exports=f()}else if(typeof define==="function"&&define.amd){define([],f)}else{var g;if(typeof window!=="undefined"){g=window}else if(typeof global!=="undefined"){g=global}else if(typeof self!=="undefined"){g=self}else{g=this}g.morphdom = f()}})(function(){var define,module,exports;return (function e(t,n,r){function s(o,u){if(!n[o]){if(!t[o]){var a=typeof require=="function"&&require;if(!u&&a)return a(o,!0);if(i)return i(o,!0);var f=new Error("Cannot find module '"+o+"'");throw f.code="MODULE_NOT_FOUND",f}var l=n[o]={exports:{}};t[o][0].call(l.exports,function(e){var n=t[o][1][e];return s(n?n:e)},l,l.exports,e,t,n,r)}return n[o].exports}var i=typeof require=="function"&&require;for(var o=0;o<r.length;o++)s(r[o]);return s})({1:[function(require,module,exports){
var specialElHandlers = {
    /**
     * Needed for IE. Apparently IE doesn't think
     * that "selected" is an attribute when reading
     * over the attributes using selectEl.attributes
     */
    OPTION: function(fromEl, toEl) {
        if ((fromEl.selected = toEl.selected)) {
            fromEl.setAttribute('selected', '');
        } else {
            fromEl.removeAttribute('selected', '');
        }
    },
    /**
     * The "value" attribute is special for the <input> element
     * since it sets the initial value. Changing the "value"
     * attribute without changing the "value" property will have
     * no effect since it is only used to the set the initial value.
     * Similar for the "checked" attribute.
     */
    /*INPUT: function(fromEl, toEl) {
        fromEl.checked = toEl.checked;
        fromEl.value = toEl.value;

        if (!toEl.hasAttribute('checked')) {
            fromEl.removeAttribute('checked');
        }

        if (!toEl.hasAttribute('value')) {
            fromEl.removeAttribute('value');
        }
    }*/
};

function noop() {}

/**
 * Loop over all of the attributes on the target node and make sure the
 * original DOM node has the same attributes. If an attribute
 * found on the original node is not on the new node then remove it from
 * the original node
 * @param  {HTMLElement} fromNode
 * @param  {HTMLElement} toNode
 */
function morphAttrs(fromNode, toNode) {
    var attrs = toNode.attributes;
    var i;
    var attr;
    var attrName;
    var attrValue;
    var foundAttrs = {};

    for (i=attrs.length-1; i>=0; i--) {
        attr = attrs[i];
        if (attr.specified !== false) {
            attrName = attr.name;
            attrValue = attr.value;
            foundAttrs[attrName] = true;

            if (fromNode.getAttribute(attrName) !== attrValue) {
                fromNode.setAttribute(attrName, attrValue);
            }
        }
    }

    // Delete any extra attributes found on the original DOM element that weren't
    // found on the target element.
    attrs = fromNode.attributes;

    for (i=attrs.length-1; i>=0; i--) {
        attr = attrs[i];
        if (attr.specified !== false) {
            attrName = attr.name;
            if (!foundAttrs.hasOwnProperty(attrName)) {
                fromNode.removeAttribute(attrName);
            }
        }
    }
}

/**
 * Copies the children of one DOM element to another DOM element
 */
function moveChildren(from, to) {
    var curChild = from.firstChild;
    while(curChild) {
        var nextChild = curChild.nextSibling;
        to.appendChild(curChild);
        curChild = nextChild;
    }
    return to;
}

function morphdom(fromNode, toNode, options) {
    if (!options) {
        options = {};
    }

    if (typeof toNode === 'string') {
        var newBodyEl = document.createElement('body');
        newBodyEl.innerHTML = toNode;
        toNode = newBodyEl.childNodes[0];
    }

    var savedEls = {}; // Used to save off DOM elements with IDs
    var unmatchedEls = {};
    var onNodeDiscarded = options.onNodeDiscarded || noop;
    var onBeforeMorphEl = options.onBeforeMorphEl || noop;
    var onBeforeMorphElChildren = options.onBeforeMorphElChildren || noop;

    function removeNodeHelper(node, nestedInSavedEl) {
        var id = node.id;
        // If the node has an ID then save it off since we will want
        // to reuse it in case the target DOM tree has a DOM element
        // with the same ID
        if (id) {
            savedEls[id] = node;
        } else if (!nestedInSavedEl) {
            // If we are not nested in a saved element then we know that this node has been
            // completely discarded and will not exist in the final DOM.
            onNodeDiscarded(node);
        }

        if (node.nodeType === 1) {
            var curChild = node.firstChild;
            while(curChild) {
                removeNodeHelper(curChild, nestedInSavedEl || id);
                curChild = curChild.nextSibling;
            }
        }
    }

    function walkDiscardedChildNodes(node) {
        if (node.nodeType === 1) {
            var curChild = node.firstChild;
            while(curChild) {


                if (!curChild.id) {
                    // We only want to handle nodes that don't have an ID to avoid double
                    // walking the same saved element.

                    onNodeDiscarded(curChild);

                    // Walk recursively
                    walkDiscardedChildNodes(curChild);
                }

                curChild = curChild.nextSibling;
            }
        }
    }

    function removeNode(node, parentNode, alreadyVisited) {
        parentNode.removeChild(node);

        if (alreadyVisited) {
            if (!node.id) {
                onNodeDiscarded(node);
                walkDiscardedChildNodes(node);
            }
        } else {
            removeNodeHelper(node);
        }
    }

    function morphEl(fromNode, toNode, alreadyVisited) {
        if (toNode.id) {
            // If an element with an ID is being morphed then it is will be in the final
            // DOM so clear it out of the saved elements collection
            delete savedEls[toNode.id];
        }

        if (onBeforeMorphEl(fromNode, toNode) === false) {
            return;
        }

        morphAttrs(fromNode, toNode);

        if (onBeforeMorphElChildren(fromNode, toNode) === false) {
            return;
        }

        var curToNodeChild = toNode.firstChild;
        var curFromNodeChild = fromNode.firstChild;
        var curToNodeId;

        var fromNextSibling;
        var toNextSibling;
        var savedEl;
        var unmatchedEl;

        outer: while(curToNodeChild) {
            toNextSibling = curToNodeChild.nextSibling;
            curToNodeId = curToNodeChild.id;

            while(curFromNodeChild) {
                var curFromNodeId = curFromNodeChild.id;
                fromNextSibling = curFromNodeChild.nextSibling;

                if (!alreadyVisited) {
                    if (curFromNodeId && (unmatchedEl = unmatchedEls[curFromNodeId])) {
                        unmatchedEl.parentNode.replaceChild(curFromNodeChild, unmatchedEl);
                        morphEl(curFromNodeChild, unmatchedEl, alreadyVisited);
                        curFromNodeChild = fromNextSibling;
                        continue;
                    }
                }

                var curFromNodeType = curFromNodeChild.nodeType;

                if (curFromNodeType === curToNodeChild.nodeType) {
                    var isCompatible = false;

                    if (curFromNodeType === 1) { // Both nodes being compared are Element nodes
                        if (curFromNodeChild.tagName === curToNodeChild.tagName) {
                            // We have compatible DOM elements
                            if (curFromNodeId || curToNodeId) {
                                // If either DOM element has an ID then we handle
                                // those differently since we want to match up
                                // by ID
                                if (curToNodeId === curFromNodeId) {
                                    isCompatible = true;
                                }
                            } else {
                                isCompatible = true;
                            }
                        }

                        if (isCompatible) {
                            // We found compatible DOM elements so add a
                            // task to morph the compatible DOM elements
                            morphEl(curFromNodeChild, curToNodeChild, alreadyVisited);
                        }
                    } else if (curFromNodeType === 3) { // Both nodes being compared are Text nodes
                        isCompatible = true;
                        curFromNodeChild.nodeValue = curToNodeChild.nodeValue;
                    }

                    if (isCompatible) {
                        curToNodeChild = toNextSibling;
                        curFromNodeChild = fromNextSibling;
                        continue outer;
                    }
                }

                // No compatible match so remove the old node from the DOM
                removeNode(curFromNodeChild, fromNode, alreadyVisited);

                curFromNodeChild = fromNextSibling;
            }

            if (curToNodeId) {
                if ((savedEl = savedEls[curToNodeId])) {
                    morphEl(savedEl, curToNodeChild, true);
                    curToNodeChild = savedEl; // We want to append the saved element instead
                } else {
                    // The current DOM element in the target tree has an ID
                    // but we did not find a match in any of the corresponding
                    // siblings. We just put the target element in the old DOM tree
                    // but if we later find an element in the old DOM tree that has
                    // a matching ID then we will replace the target element
                    // with the corresponding old element and morph the old element
                    unmatchedEls[curToNodeId] = curToNodeChild;
                }
            }

            // If we got this far then we did not find a candidate match for our "to node"
            // and we exhausted all of the children "from" nodes. Therefore, we will just
            // append the current "to node" to the end
            fromNode.appendChild(curToNodeChild);

            curToNodeChild = toNextSibling;
            curFromNodeChild = fromNextSibling;
        }

        // We have processed all of the "to nodes". If curFromNodeChild is non-null then
        // we still have some from nodes left over that need to be removed
        while(curFromNodeChild) {
            fromNextSibling = curFromNodeChild.nextSibling;
            removeNode(curFromNodeChild, fromNode, alreadyVisited);
            curFromNodeChild = fromNextSibling;
        }

        var specialElHandler = specialElHandlers[fromNode.tagName];
        if (specialElHandler) {
            specialElHandler(fromNode, toNode);
        }
    }

    var morphedNode = fromNode;
    var morphedNodeType = morphedNode.nodeType;
    var toNodeType = toNode.nodeType;

    // Handle the case where we are given two DOM nodes that are not
    // compatible (e.g. <div> --> <span> or <div> --> TEXT)
    if (morphedNodeType === 1) {
        if (toNodeType === 1) {
            if (morphedNode.tagName !== toNode.tagName) {
                onNodeDiscarded(fromNode);
                morphedNode = moveChildren(morphedNode, document.createElement(toNode.tagName));
            }
        } else {
            // Going from an element node to a text node
            return toNode;
        }
    } else if (morphedNodeType === 3) { // Text node
        if (toNodeType === 3) {
            morphedNode.nodeValue = toNode.nodeValue;
            return morphedNode;
        } else {
            onNodeDiscarded(fromNode);
            // Text node to something else
            return toNode;
        }
    }

    morphEl(morphedNode, toNode, false);

    // Fire the "onNodeDiscarded" event for any saved elements
    // that never found a new home in the morphed DOM
    for (var savedElId in savedEls) {
        if (savedEls.hasOwnProperty(savedElId)) {
            var savedEl = savedEls[savedElId];
            onNodeDiscarded(savedEl);
            walkDiscardedChildNodes(savedEl);
        }
    }

    if (morphedNode !== fromNode && fromNode.parentNode) {
        fromNode.parentNode.replaceChild(morphedNode, fromNode);
    }

    return morphedNode;
}

module.exports = morphdom;
},{}]},{},[1])(1)
});