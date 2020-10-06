
/* ---- lib/Animation.coffee ---- */


(function() {
  var Animation;

  Animation = (function() {
    function Animation() {}

    Animation.prototype.slideDown = function(elem, props) {
      var cstyle, h, margin_bottom, margin_top, padding_bottom, padding_top, transition;
      if (elem.offsetTop > 2000) {
        return;
      }
      h = elem.offsetHeight;
      cstyle = window.getComputedStyle(elem);
      margin_top = cstyle.marginTop;
      margin_bottom = cstyle.marginBottom;
      padding_top = cstyle.paddingTop;
      padding_bottom = cstyle.paddingBottom;
      transition = cstyle.transition;
      elem.style.boxSizing = "border-box";
      elem.style.overflow = "hidden";
      elem.style.transform = "scale(0.6)";
      elem.style.opacity = "0";
      elem.style.height = "0px";
      elem.style.marginTop = "0px";
      elem.style.marginBottom = "0px";
      elem.style.paddingTop = "0px";
      elem.style.paddingBottom = "0px";
      elem.style.transition = "none";
      setTimeout((function() {
        elem.className += " animate-inout";
        elem.style.height = h + "px";
        elem.style.transform = "scale(1)";
        elem.style.opacity = "1";
        elem.style.marginTop = margin_top;
        elem.style.marginBottom = margin_bottom;
        elem.style.paddingTop = padding_top;
        return elem.style.paddingBottom = padding_bottom;
      }), 1);
      return elem.addEventListener("transitionend", function() {
        elem.classList.remove("animate-inout");
        elem.style.transition = elem.style.transform = elem.style.opacity = elem.style.height = null;
        elem.style.boxSizing = elem.style.marginTop = elem.style.marginBottom = null;
        elem.style.paddingTop = elem.style.paddingBottom = elem.style.overflow = null;
        return elem.removeEventListener("transitionend", arguments.callee, false);
      });
    };

    Animation.prototype.slideUp = function(elem, remove_func, props) {
      if (elem.offsetTop > 1000) {
        return remove_func();
      }
      elem.className += " animate-back";
      elem.style.boxSizing = "border-box";
      elem.style.height = elem.offsetHeight + "px";
      elem.style.overflow = "hidden";
      elem.style.transform = "scale(1)";
      elem.style.opacity = "1";
      elem.style.pointerEvents = "none";
      setTimeout((function() {
        elem.style.height = "0px";
        elem.style.marginTop = "0px";
        elem.style.marginBottom = "0px";
        elem.style.paddingTop = "0px";
        elem.style.paddingBottom = "0px";
        elem.style.transform = "scale(0.8)";
        elem.style.borderTopWidth = "0px";
        elem.style.borderBottomWidth = "0px";
        return elem.style.opacity = "0";
      }), 1);
      return elem.addEventListener("transitionend", function(e) {
        if (e.propertyName === "opacity" || e.elapsedTime >= 0.6) {
          elem.removeEventListener("transitionend", arguments.callee, false);
          return remove_func();
        }
      });
    };

    Animation.prototype.slideUpInout = function(elem, remove_func, props) {
      elem.className += " animate-inout";
      elem.style.boxSizing = "border-box";
      elem.style.height = elem.offsetHeight + "px";
      elem.style.overflow = "hidden";
      elem.style.transform = "scale(1)";
      elem.style.opacity = "1";
      elem.style.pointerEvents = "none";
      setTimeout((function() {
        elem.style.height = "0px";
        elem.style.marginTop = "0px";
        elem.style.marginBottom = "0px";
        elem.style.paddingTop = "0px";
        elem.style.paddingBottom = "0px";
        elem.style.transform = "scale(0.8)";
        elem.style.borderTopWidth = "0px";
        elem.style.borderBottomWidth = "0px";
        return elem.style.opacity = "0";
      }), 1);
      return elem.addEventListener("transitionend", function(e) {
        if (e.propertyName === "opacity" || e.elapsedTime >= 0.6) {
          elem.removeEventListener("transitionend", arguments.callee, false);
          return remove_func();
        }
      });
    };

    Animation.prototype.showRight = function(elem, props) {
      elem.className += " animate";
      elem.style.opacity = 0;
      elem.style.transform = "TranslateX(-20px) Scale(1.01)";
      setTimeout((function() {
        elem.style.opacity = 1;
        return elem.style.transform = "TranslateX(0px) Scale(1)";
      }), 1);
      return elem.addEventListener("transitionend", function() {
        elem.classList.remove("animate");
        return elem.style.transform = elem.style.opacity = null;
      });
    };

    Animation.prototype.show = function(elem, props) {
      var delay, ref;
      delay = ((ref = arguments[arguments.length - 2]) != null ? ref.delay : void 0) * 1000 || 1;
      elem.style.opacity = 0;
      setTimeout((function() {
        return elem.className += " animate";
      }), 1);
      setTimeout((function() {
        return elem.style.opacity = 1;
      }), delay);
      return elem.addEventListener("transitionend", function() {
        elem.classList.remove("animate");
        elem.style.opacity = null;
        return elem.removeEventListener("transitionend", arguments.callee, false);
      });
    };

    Animation.prototype.hide = function(elem, remove_func, props) {
      var delay, ref;
      delay = ((ref = arguments[arguments.length - 2]) != null ? ref.delay : void 0) * 1000 || 1;
      elem.className += " animate";
      setTimeout((function() {
        return elem.style.opacity = 0;
      }), delay);
      return elem.addEventListener("transitionend", function(e) {
        if (e.propertyName === "opacity") {
          return remove_func();
        }
      });
    };

    Animation.prototype.addVisibleClass = function(elem, props) {
      return setTimeout(function() {
        return elem.classList.add("visible");
      });
    };

    return Animation;

  })();

  window.Animation = new Animation();

}).call(this);

/* ---- lib/Class.coffee ---- */


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

/* ---- lib/Dollar.coffee ---- */


(function() {
  window.$ = function(selector) {
    if (selector.startsWith("#")) {
      return document.getElementById(selector.replace("#", ""));
    }
  };

}).call(this);

/* ---- lib/ItemList.coffee ---- */


(function() {
  var ItemList;

  ItemList = (function() {
    function ItemList(item_class1, key1) {
      this.item_class = item_class1;
      this.key = key1;
      this.items = [];
      this.items_bykey = {};
    }

    ItemList.prototype.sync = function(rows, item_class, key) {
      var current_obj, i, item, len, results, row;
      this.items.splice(0, this.items.length);
      results = [];
      for (i = 0, len = rows.length; i < len; i++) {
        row = rows[i];
        current_obj = this.items_bykey[row[this.key]];
        if (current_obj) {
          current_obj.row = row;
          results.push(this.items.push(current_obj));
        } else {
          item = new this.item_class(row, this);
          this.items_bykey[row[this.key]] = item;
          results.push(this.items.push(item));
        }
      }
      return results;
    };

    ItemList.prototype.deleteItem = function(item) {
      var index;
      index = this.items.indexOf(item);
      if (index > -1) {
        this.items.splice(index, 1);
      } else {
        console.log("Can't delete item", item);
      }
      return delete this.items_bykey[item.row[this.key]];
    };

    return ItemList;

  })();

  window.ItemList = ItemList;

}).call(this);

/* ---- lib/Menu.coffee ---- */


(function() {
  var Menu,
    bind = function(fn, me){ return function(){ return fn.apply(me, arguments); }; },
    indexOf = [].indexOf || function(item) { for (var i = 0, l = this.length; i < l; i++) { if (i in this && this[i] === item) return i; } return -1; };

  Menu = (function() {
    function Menu() {
      this.render = bind(this.render, this);
      this.getStyle = bind(this.getStyle, this);
      this.renderItem = bind(this.renderItem, this);
      this.handleClick = bind(this.handleClick, this);
      this.getDirection = bind(this.getDirection, this);
      this.storeNode = bind(this.storeNode, this);
      this.toggle = bind(this.toggle, this);
      this.hide = bind(this.hide, this);
      this.show = bind(this.show, this);
      this.visible = false;
      this.items = [];
      this.node = null;
      this.height = 0;
      this.direction = "bottom";
    }

    Menu.prototype.show = function() {
      var ref;
      if ((ref = window.visible_menu) != null) {
        ref.hide();
      }
      this.visible = true;
      window.visible_menu = this;
      return this.direction = this.getDirection();
    };

    Menu.prototype.hide = function() {
      return this.visible = false;
    };

    Menu.prototype.toggle = function() {
      if (this.visible) {
        this.hide();
      } else {
        this.show();
      }
      return Page.projector.scheduleRender();
    };

    Menu.prototype.addItem = function(title, cb, selected) {
      if (selected == null) {
        selected = false;
      }
      return this.items.push([title, cb, selected]);
    };

    Menu.prototype.storeNode = function(node) {
      this.node = node;
      if (this.visible) {
        node.className = node.className.replace("visible", "");
        setTimeout(((function(_this) {
          return function() {
            node.className += " visible";
            return node.attributes.style.value = _this.getStyle();
          };
        })(this)), 20);
        node.style.maxHeight = "none";
        this.height = node.offsetHeight;
        node.style.maxHeight = "0px";
        return this.direction = this.getDirection();
      }
    };

    Menu.prototype.getDirection = function() {
      if (this.node && this.node.parentNode.getBoundingClientRect().top + this.height + 60 > document.body.clientHeight && this.node.parentNode.getBoundingClientRect().top - this.height > 0) {
        return "top";
      } else {
        return "bottom";
      }
    };

    Menu.prototype.handleClick = function(e) {
      var cb, i, item, keep_menu, len, ref, selected, title;
      keep_menu = false;
      ref = this.items;
      for (i = 0, len = ref.length; i < len; i++) {
        item = ref[i];
        title = item[0], cb = item[1], selected = item[2];
        if (title === e.currentTarget.textContent || e.currentTarget["data-title"] === title) {
          keep_menu = typeof cb === "function" ? cb(item) : void 0;
          break;
        }
      }
      if (keep_menu !== true && cb !== null) {
        this.hide();
      }
      return false;
    };

    Menu.prototype.renderItem = function(item) {
      var cb, classes, href, onclick, selected, title;
      title = item[0], cb = item[1], selected = item[2];
      if (typeof selected === "function") {
        selected = selected();
      }
      if (title === "---") {
        return h("div.menu-item-separator", {
          key: Time.timestamp()
        });
      } else {
        if (cb === null) {
          href = void 0;
          onclick = this.handleClick;
        } else if (typeof cb === "string") {
          href = cb;
          onclick = true;
        } else {
          href = "#" + title;
          onclick = this.handleClick;
        }
        classes = {
          "selected": selected,
          "noaction": cb === null
        };
        return h("a.menu-item", {
          href: href,
          onclick: onclick,
          "data-title": title,
          key: title,
          classes: classes
        }, title);
      }
    };

    Menu.prototype.getStyle = function() {
      var max_height, style;
      if (this.visible) {
        max_height = this.height;
      } else {
        max_height = 0;
      }
      style = "max-height: " + max_height + "px";
      if (this.direction === "top") {
        style += ";margin-top: " + (0 - this.height - 50) + "px";
      } else {
        style += ";margin-top: 0px";
      }
      return style;
    };

    Menu.prototype.render = function(class_name) {
      if (class_name == null) {
        class_name = "";
      }
      if (this.visible || this.node) {
        return h("div.menu" + class_name, {
          classes: {
            "visible": this.visible
          },
          style: this.getStyle(),
          afterCreate: this.storeNode
        }, this.items.map(this.renderItem));
      }
    };

    return Menu;

  })();

  window.Menu = Menu;

  document.body.addEventListener("mouseup", function(e) {
    var menu_node, menu_parents, ref, ref1;
    if (!window.visible_menu || !window.visible_menu.node) {
      return false;
    }
    menu_node = window.visible_menu.node;
    menu_parents = [menu_node, menu_node.parentNode];
    if ((ref = e.target.parentNode, indexOf.call(menu_parents, ref) < 0) && (ref1 = e.target.parentNode.parentNode, indexOf.call(menu_parents, ref1) < 0)) {
      window.visible_menu.hide();
      return Page.projector.scheduleRender();
    }
  });

}).call(this);

/* ---- lib/Promise.coffee ---- */


(function() {
  var Promise,
    slice = [].slice;

  Promise = (function() {
    Promise.when = function() {
      var args, fn, i, len, num_uncompleted, promise, task, task_id, tasks;
      tasks = 1 <= arguments.length ? slice.call(arguments, 0) : [];
      num_uncompleted = tasks.length;
      args = new Array(num_uncompleted);
      promise = new Promise();
      fn = function(task_id) {
        return task.then(function() {
          args[task_id] = Array.prototype.slice.call(arguments);
          num_uncompleted--;
          if (num_uncompleted === 0) {
            return promise.complete.apply(promise, args);
          }
        });
      };
      for (task_id = i = 0, len = tasks.length; i < len; task_id = ++i) {
        task = tasks[task_id];
        fn(task_id);
      }
      return promise;
    };

    function Promise() {
      this.resolved = false;
      this.end_promise = null;
      this.result = null;
      this.callbacks = [];
    }

    Promise.prototype.resolve = function() {
      var back, callback, i, len, ref;
      if (this.resolved) {
        return false;
      }
      this.resolved = true;
      this.data = arguments;
      if (!arguments.length) {
        this.data = [true];
      }
      this.result = this.data[0];
      ref = this.callbacks;
      for (i = 0, len = ref.length; i < len; i++) {
        callback = ref[i];
        back = callback.apply(callback, this.data);
      }
      if (this.end_promise) {
        return this.end_promise.resolve(back);
      }
    };

    Promise.prototype.fail = function() {
      return this.resolve(false);
    };

    Promise.prototype.then = function(callback) {
      if (this.resolved === true) {
        callback.apply(callback, this.data);
        return;
      }
      this.callbacks.push(callback);
      return this.end_promise = new Promise();
    };

    return Promise;

  })();

  window.Promise = Promise;


  /*
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
   */

}).call(this);

/* ---- lib/Prototypes.coffee ---- */


(function() {
  String.prototype.startsWith = function(s) {
    return this.slice(0, s.length) === s;
  };

  String.prototype.endsWith = function(s) {
    return s === '' || this.slice(-s.length) === s;
  };

  String.prototype.repeat = function(count) {
    return new Array(count + 1).join(this);
  };

  window.isEmpty = function(obj) {
    var key;
    for (key in obj) {
      return false;
    }
    return true;
  };

}).call(this);

/* ---- lib/RateLimitCb.coffee ---- */


(function() {
  var call_after_interval, calling, calling_iterval, last_time,
    slice = [].slice;

  last_time = {};

  calling = {};

  calling_iterval = {};

  call_after_interval = {};

  window.RateLimitCb = function(interval, fn, args) {
    var cb;
    if (args == null) {
      args = [];
    }
    cb = function() {
      var left;
      left = interval - (Date.now() - last_time[fn]);
      if (left <= 0) {
        delete last_time[fn];
        if (calling[fn]) {
          RateLimitCb(interval, fn, calling[fn]);
        }
        return delete calling[fn];
      } else {
        return setTimeout((function() {
          delete last_time[fn];
          if (calling[fn]) {
            RateLimitCb(interval, fn, calling[fn]);
          }
          return delete calling[fn];
        }), left);
      }
    };
    if (last_time[fn]) {
      return calling[fn] = args;
    } else {
      last_time[fn] = Date.now();
      return fn.apply(this, [cb].concat(slice.call(args)));
    }
  };

  window.RateLimit = function(interval, fn) {
    if (calling_iterval[fn] > interval) {
      clearInterval(calling[fn]);
      delete calling[fn];
    }
    if (!calling[fn]) {
      call_after_interval[fn] = false;
      fn();
      calling_iterval[fn] = interval;
      return calling[fn] = setTimeout((function() {
        if (call_after_interval[fn]) {
          fn();
        }
        delete calling[fn];
        return delete call_after_interval[fn];
      }), interval);
    } else {
      return call_after_interval[fn] = true;
    }
  };


  /*
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
   */

}).call(this);

/* ---- lib/Text.coffee ---- */


(function() {
  var Text,
    indexOf = [].indexOf || function(item) { for (var i = 0, l = this.length; i < l; i++) { if (i in this && this[i] === item) return i; } return -1; };

  Text = (function() {
    function Text() {}

    Text.prototype.toColor = function(text, saturation, lightness) {
      var hash, i, j, ref;
      if (saturation == null) {
        saturation = 30;
      }
      if (lightness == null) {
        lightness = 50;
      }
      hash = 0;
      for (i = j = 0, ref = text.length - 1; 0 <= ref ? j <= ref : j >= ref; i = 0 <= ref ? ++j : --j) {
        hash += text.charCodeAt(i) * i;
        hash = hash % 1777;
      }
      return "hsl(" + (hash % 360) + ("," + saturation + "%," + lightness + "%)");
    };

    Text.prototype.renderMarked = function(text, options) {
      if (options == null) {
        options = {};
      }
      options["gfm"] = true;
      options["breaks"] = true;
      options["sanitize"] = true;
      options["renderer"] = marked_renderer;
      text = marked(text, options);
      return this.fixHtmlLinks(text);
    };

    Text.prototype.emailLinks = function(text) {
      return text.replace(/([a-zA-Z0-9]+)@zeroid.bit/g, "<a href='?to=$1' onclick='return Page.message_create.show(\"$1\")'>$1@zeroid.bit</a>");
    };

    Text.prototype.fixHtmlLinks = function(text) {
      if (window.is_proxy) {
        return text.replace(/href="http:\/\/(127.0.0.1|localhost):43110/g, 'href="http://zero');
      } else {
        return text.replace(/href="http:\/\/(127.0.0.1|localhost):43110/g, 'href="');
      }
    };

    Text.prototype.fixLink = function(link) {
      var back;
      if (window.is_proxy) {
        back = link.replace(/http:\/\/(127.0.0.1|localhost):43110/, 'http://zero');
        return back.replace(/http:\/\/zero\/([^\/]+\.bit)/, "http://$1");
      } else {
        return link.replace(/http:\/\/(127.0.0.1|localhost):43110/, '');
      }
    };

    Text.prototype.toUrl = function(text) {
      return text.replace(/[^A-Za-z0-9]/g, "+").replace(/[+]+/g, "+").replace(/[+]+$/, "");
    };

    Text.prototype.getSiteUrl = function(address) {
      if (window.is_proxy) {
        if (indexOf.call(address, ".") >= 0) {
          return "http://" + address + "/";
        } else {
          return "http://zero/" + address + "/";
        }
      } else {
        return "/" + address + "/";
      }
    };

    Text.prototype.fixReply = function(text) {
      return text.replace(/(>.*\n)([^\n>])/gm, "$1\n$2");
    };

    Text.prototype.toBitcoinAddress = function(text) {
      return text.replace(/[^A-Za-z0-9]/g, "");
    };

    Text.prototype.jsonEncode = function(obj) {
      return unescape(encodeURIComponent(JSON.stringify(obj)));
    };

    Text.prototype.jsonDecode = function(obj) {
      return JSON.parse(decodeURIComponent(escape(obj)));
    };

    Text.prototype.fileEncode = function(obj) {
      if (typeof obj === "string") {
        return btoa(unescape(encodeURIComponent(obj)));
      } else {
        return btoa(unescape(encodeURIComponent(JSON.stringify(obj, void 0, '\t'))));
      }
    };

    Text.prototype.utf8Encode = function(s) {
      return unescape(encodeURIComponent(s));
    };

    Text.prototype.utf8Decode = function(s) {
      return decodeURIComponent(escape(s));
    };

    Text.prototype.distance = function(s1, s2) {
      var char, extra_parts, j, key, len, match, next_find, next_find_i, val;
      s1 = s1.toLocaleLowerCase();
      s2 = s2.toLocaleLowerCase();
      next_find_i = 0;
      next_find = s2[0];
      match = true;
      extra_parts = {};
      for (j = 0, len = s1.length; j < len; j++) {
        char = s1[j];
        if (char !== next_find) {
          if (extra_parts[next_find_i]) {
            extra_parts[next_find_i] += char;
          } else {
            extra_parts[next_find_i] = char;
          }
        } else {
          next_find_i++;
          next_find = s2[next_find_i];
        }
      }
      if (extra_parts[next_find_i]) {
        extra_parts[next_find_i] = "";
      }
      extra_parts = (function() {
        var results;
        results = [];
        for (key in extra_parts) {
          val = extra_parts[key];
          results.push(val);
        }
        return results;
      })();
      if (next_find_i >= s2.length) {
        return extra_parts.length + extra_parts.join("").length;
      } else {
        return false;
      }
    };

    Text.prototype.parseQuery = function(query) {
      var j, key, len, params, part, parts, ref, val;
      params = {};
      parts = query.split('&');
      for (j = 0, len = parts.length; j < len; j++) {
        part = parts[j];
        ref = part.split("="), key = ref[0], val = ref[1];
        if (val) {
          params[decodeURIComponent(key)] = decodeURIComponent(val);
        } else {
          params["url"] = decodeURIComponent(key);
        }
      }
      return params;
    };

    Text.prototype.encodeQuery = function(params) {
      var back, key, val;
      back = [];
      if (params.url) {
        back.push(params.url);
      }
      for (key in params) {
        val = params[key];
        if (!val || key === "url") {
          continue;
        }
        back.push((encodeURIComponent(key)) + "=" + (encodeURIComponent(val)));
      }
      return back.join("&");
    };

    Text.prototype.highlight = function(text, search) {
      var back, i, j, len, part, parts;
      if (!text) {
        return [""];
      }
      parts = text.split(RegExp(search, "i"));
      back = [];
      for (i = j = 0, len = parts.length; j < len; i = ++j) {
        part = parts[i];
        back.push(part);
        if (i < parts.length - 1) {
          back.push(h("span.highlight", {
            key: i
          }, search));
        }
      }
      return back;
    };

    Text.prototype.formatSize = function(size) {
      var size_mb;
      if (isNaN(parseInt(size))) {
        return "";
      }
      size_mb = size / 1024 / 1024;
      if (size_mb >= 1000) {
        return (size_mb / 1024).toFixed(1) + " GB";
      } else if (size_mb >= 100) {
        return size_mb.toFixed(0) + " MB";
      } else if (size / 1024 >= 1000) {
        return size_mb.toFixed(2) + " MB";
      } else {
        return (parseInt(size) / 1024).toFixed(2) + " KB";
      }
    };

    return Text;

  })();

  window.is_proxy = document.location.host === "zero" || window.location.pathname === "/";

  window.Text = new Text();

}).call(this);

/* ---- lib/Time.coffee ---- */


(function() {
  var Time;

  Time = (function() {
    function Time() {}

    Time.prototype.since = function(timestamp) {
      var back, minutes, now, secs;
      now = +(new Date) / 1000;
      if (timestamp > 1000000000000) {
        timestamp = timestamp / 1000;
      }
      secs = now - timestamp;
      if (secs < 60) {
        back = "Just now";
      } else if (secs < 60 * 60) {
        minutes = Math.round(secs / 60);
        back = "" + minutes + " minutes ago";
      } else if (secs < 60 * 60 * 24) {
        back = (Math.round(secs / 60 / 60)) + " hours ago";
      } else if (secs < 60 * 60 * 24 * 3) {
        back = (Math.round(secs / 60 / 60 / 24)) + " days ago";
      } else {
        back = "on " + this.date(timestamp);
      }
      back = back.replace(/^1 ([a-z]+)s/, "1 $1");
      return back;
    };

    Time.prototype.dateIso = function(timestamp) {
      var tzoffset;
      if (timestamp == null) {
        timestamp = null;
      }
      if (!timestamp) {
        timestamp = window.Time.timestamp();
      }
      if (timestamp > 1000000000000) {
        timestamp = timestamp / 1000;
      }
      tzoffset = (new Date()).getTimezoneOffset() * 60;
      return (new Date((timestamp - tzoffset) * 1000)).toISOString().split("T")[0];
    };

    Time.prototype.date = function(timestamp, format) {
      var display, parts;
      if (timestamp == null) {
        timestamp = null;
      }
      if (format == null) {
        format = "short";
      }
      if (!timestamp) {
        timestamp = window.Time.timestamp();
      }
      if (timestamp > 1000000000000) {
        timestamp = timestamp / 1000;
      }
      parts = (new Date(timestamp * 1000)).toString().split(" ");
      if (format === "short") {
        display = parts.slice(1, 4);
      } else if (format === "day") {
        display = parts.slice(1, 3);
      } else if (format === "month") {
        display = [parts[1], parts[3]];
      } else if (format === "long") {
        display = parts.slice(1, 5);
      }
      return display.join(" ").replace(/( [0-9]{4})/, ",$1");
    };

    Time.prototype.weekDay = function(timestamp) {
      if (timestamp > 1000000000000) {
        timestamp = timestamp / 1000;
      }
      return ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"][(new Date(timestamp * 1000)).getDay()];
    };

    Time.prototype.timestamp = function(date) {
      if (date == null) {
        date = "";
      }
      if (date === "now" || date === "") {
        return parseInt(+(new Date) / 1000);
      } else {
        return parseInt(Date.parse(date) / 1000);
      }
    };

    return Time;

  })();

  window.Time = new Time;

}).call(this);

/* ---- lib/ZeroFrame.coffee ---- */


(function() {
  var ZeroFrame,
    bind = function(fn, me){ return function(){ return fn.apply(me, arguments); }; },
    extend = function(child, parent) { for (var key in parent) { if (hasProp.call(parent, key)) child[key] = parent[key]; } function ctor() { this.constructor = child; } ctor.prototype = parent.prototype; child.prototype = new ctor(); child.__super__ = parent.prototype; return child; },
    hasProp = {}.hasOwnProperty;

  ZeroFrame = (function(superClass) {
    extend(ZeroFrame, superClass);

    function ZeroFrame(url) {
      this.onCloseWebsocket = bind(this.onCloseWebsocket, this);
      this.onOpenWebsocket = bind(this.onOpenWebsocket, this);
      this.onRequest = bind(this.onRequest, this);
      this.onMessage = bind(this.onMessage, this);
      this.url = url;
      this.waiting_cb = {};
      this.wrapper_nonce = document.location.href.replace(/.*wrapper_nonce=([A-Za-z0-9]+).*/, "$1");
      this.connect();
      this.next_message_id = 1;
      this.history_state = {};
      this.init();
    }

    ZeroFrame.prototype.init = function() {
      return this;
    };

    ZeroFrame.prototype.connect = function() {
      this.target = window.parent;
      window.addEventListener("message", this.onMessage, false);
      this.cmd("innerReady");
      window.addEventListener("beforeunload", (function(_this) {
        return function(e) {
          _this.log("save scrollTop", window.pageYOffset);
          _this.history_state["scrollTop"] = window.pageYOffset;
          return _this.cmd("wrapperReplaceState", [_this.history_state, null]);
        };
      })(this));
      return this.cmd("wrapperGetState", [], (function(_this) {
        return function(state) {
          if (state != null) {
            _this.history_state = state;
          }
          _this.log("restore scrollTop", state, window.pageYOffset);
          if (window.pageYOffset === 0 && state) {
            return window.scroll(window.pageXOffset, state.scrollTop);
          }
        };
      })(this));
    };

    ZeroFrame.prototype.onMessage = function(e) {
      var cmd, message;
      message = e.data;
      cmd = message.cmd;
      if (cmd === "response") {
        if (this.waiting_cb[message.to] != null) {
          return this.waiting_cb[message.to](message.result);
        } else {
          return this.log("Websocket callback not found:", message);
        }
      } else if (cmd === "wrapperReady") {
        return this.cmd("innerReady");
      } else if (cmd === "ping") {
        return this.response(message.id, "pong");
      } else if (cmd === "wrapperOpenedWebsocket") {
        return this.onOpenWebsocket();
      } else if (cmd === "wrapperClosedWebsocket") {
        return this.onCloseWebsocket();
      } else {
        return this.onRequest(cmd, message.params);
      }
    };

    ZeroFrame.prototype.onRequest = function(cmd, message) {
      return this.log("Unknown request", message);
    };

    ZeroFrame.prototype.response = function(to, result) {
      return this.send({
        "cmd": "response",
        "to": to,
        "result": result
      });
    };

    ZeroFrame.prototype.cmd = function(cmd, params, cb) {
      if (params == null) {
        params = {};
      }
      if (cb == null) {
        cb = null;
      }
      return this.send({
        "cmd": cmd,
        "params": params
      }, cb);
    };

    ZeroFrame.prototype.send = function(message, cb) {
      if (cb == null) {
        cb = null;
      }
      message.wrapper_nonce = this.wrapper_nonce;
      message.id = this.next_message_id;
      this.next_message_id += 1;
      this.target.postMessage(message, "*");
      if (cb) {
        return this.waiting_cb[message.id] = cb;
      }
    };

    ZeroFrame.prototype.onOpenWebsocket = function() {
      return this.log("Websocket open");
    };

    ZeroFrame.prototype.onCloseWebsocket = function() {
      return this.log("Websocket close");
    };

    return ZeroFrame;

  })(Class);

  window.ZeroFrame = ZeroFrame;

}).call(this);

/* ---- lib/maquette.js ---- */


(function (root, factory) {
    if (typeof define === 'function' && define.amd) {
        // AMD. Register as an anonymous module.
        define(['exports'], factory);
    } else if (typeof exports === 'object' && typeof exports.nodeName !== 'string') {
        // CommonJS
        factory(exports);
    } else {
        // Browser globals
        factory(root.maquette = {});
    }
}(this, function (exports) {
    'use strict';
    ;
    ;
    ;
    ;
    var NAMESPACE_W3 = 'http://www.w3.org/';
    var NAMESPACE_SVG = NAMESPACE_W3 + '2000/svg';
    var NAMESPACE_XLINK = NAMESPACE_W3 + '1999/xlink';
    // Utilities
    var emptyArray = [];
    var extend = function (base, overrides) {
        var result = {};
        Object.keys(base).forEach(function (key) {
            result[key] = base[key];
        });
        if (overrides) {
            Object.keys(overrides).forEach(function (key) {
                result[key] = overrides[key];
            });
        }
        return result;
    };
    // Hyperscript helper functions
    var same = function (vnode1, vnode2) {
        if (vnode1.vnodeSelector !== vnode2.vnodeSelector) {
            return false;
        }
        if (vnode1.properties && vnode2.properties) {
            if (vnode1.properties.key !== vnode2.properties.key) {
                return false;
            }
            return vnode1.properties.bind === vnode2.properties.bind;
        }
        return !vnode1.properties && !vnode2.properties;
    };
    var toTextVNode = function (data) {
        return {
            vnodeSelector: '',
            properties: undefined,
            children: undefined,
            text: data.toString(),
            domNode: null
        };
    };
    var appendChildren = function (parentSelector, insertions, main) {
        for (var i = 0; i < insertions.length; i++) {
            var item = insertions[i];
            if (Array.isArray(item)) {
                appendChildren(parentSelector, item, main);
            } else {
                if (item !== null && item !== undefined) {
                    if (!item.hasOwnProperty('vnodeSelector')) {
                        item = toTextVNode(item);
                    }
                    main.push(item);
                }
            }
        }
    };
    // Render helper functions
    var missingTransition = function () {
        throw new Error('Provide a transitions object to the projectionOptions to do animations');
    };
    var DEFAULT_PROJECTION_OPTIONS = {
        namespace: undefined,
        eventHandlerInterceptor: undefined,
        styleApplyer: function (domNode, styleName, value) {
            // Provides a hook to add vendor prefixes for browsers that still need it.
            domNode.style[styleName] = value;
        },
        transitions: {
            enter: missingTransition,
            exit: missingTransition
        }
    };
    var applyDefaultProjectionOptions = function (projectorOptions) {
        return extend(DEFAULT_PROJECTION_OPTIONS, projectorOptions);
    };
    var checkStyleValue = function (styleValue) {
        if (typeof styleValue !== 'string') {
            throw new Error('Style values must be strings');
        }
    };
    var setProperties = function (domNode, properties, projectionOptions) {
        if (!properties) {
            return;
        }
        var eventHandlerInterceptor = projectionOptions.eventHandlerInterceptor;
        var propNames = Object.keys(properties);
        var propCount = propNames.length;
        for (var i = 0; i < propCount; i++) {
            var propName = propNames[i];
            /* tslint:disable:no-var-keyword: edge case */
            var propValue = properties[propName];
            /* tslint:enable:no-var-keyword */
            if (propName === 'className') {
                throw new Error('Property "className" is not supported, use "class".');
            } else if (propName === 'class') {
                if (domNode.className) {
                    // May happen if classes is specified before class
                    domNode.className += ' ' + propValue;
                } else {
                    domNode.className = propValue;
                }
            } else if (propName === 'classes') {
                // object with string keys and boolean values
                var classNames = Object.keys(propValue);
                var classNameCount = classNames.length;
                for (var j = 0; j < classNameCount; j++) {
                    var className = classNames[j];
                    if (propValue[className]) {
                        domNode.classList.add(className);
                    }
                }
            } else if (propName === 'styles') {
                // object with string keys and string (!) values
                var styleNames = Object.keys(propValue);
                var styleCount = styleNames.length;
                for (var j = 0; j < styleCount; j++) {
                    var styleName = styleNames[j];
                    var styleValue = propValue[styleName];
                    if (styleValue) {
                        checkStyleValue(styleValue);
                        projectionOptions.styleApplyer(domNode, styleName, styleValue);
                    }
                }
            } else if (propName === 'key') {
                continue;
            } else if (propValue === null || propValue === undefined) {
                continue;
            } else {
                var type = typeof propValue;
                if (type === 'function') {
                    if (propName.lastIndexOf('on', 0) === 0) {
                        if (eventHandlerInterceptor) {
                            propValue = eventHandlerInterceptor(propName, propValue, domNode, properties);    // intercept eventhandlers
                        }
                        if (propName === 'oninput') {
                            (function () {
                                // record the evt.target.value, because IE and Edge sometimes do a requestAnimationFrame between changing value and running oninput
                                var oldPropValue = propValue;
                                propValue = function (evt) {
                                    evt.target['oninput-value'] = evt.target.value;
                                    // may be HTMLTextAreaElement as well
                                    oldPropValue.apply(this, [evt]);
                                };
                            }());
                        }
                        domNode[propName] = propValue;
                    }
                } else if (type === 'string' && propName !== 'value' && propName !== 'innerHTML') {
                    if (projectionOptions.namespace === NAMESPACE_SVG && propName === 'href') {
                        domNode.setAttributeNS(NAMESPACE_XLINK, propName, propValue);
                    } else {
                        domNode.setAttribute(propName, propValue);
                    }
                } else {
                    domNode[propName] = propValue;
                }
            }
        }
    };
    var updateProperties = function (domNode, previousProperties, properties, projectionOptions) {
        if (!properties) {
            return;
        }
        var propertiesUpdated = false;
        var propNames = Object.keys(properties);
        var propCount = propNames.length;
        for (var i = 0; i < propCount; i++) {
            var propName = propNames[i];
            // assuming that properties will be nullified instead of missing is by design
            var propValue = properties[propName];
            var previousValue = previousProperties[propName];
            if (propName === 'class') {
                if (previousValue !== propValue) {
                    throw new Error('"class" property may not be updated. Use the "classes" property for conditional css classes.');
                }
            } else if (propName === 'classes') {
                var classList = domNode.classList;
                var classNames = Object.keys(propValue);
                var classNameCount = classNames.length;
                for (var j = 0; j < classNameCount; j++) {
                    var className = classNames[j];
                    var on = !!propValue[className];
                    var previousOn = !!previousValue[className];
                    if (on === previousOn) {
                        continue;
                    }
                    propertiesUpdated = true;
                    if (on) {
                        classList.add(className);
                    } else {
                        classList.remove(className);
                    }
                }
            } else if (propName === 'styles') {
                var styleNames = Object.keys(propValue);
                var styleCount = styleNames.length;
                for (var j = 0; j < styleCount; j++) {
                    var styleName = styleNames[j];
                    var newStyleValue = propValue[styleName];
                    var oldStyleValue = previousValue[styleName];
                    if (newStyleValue === oldStyleValue) {
                        continue;
                    }
                    propertiesUpdated = true;
                    if (newStyleValue) {
                        checkStyleValue(newStyleValue);
                        projectionOptions.styleApplyer(domNode, styleName, newStyleValue);
                    } else {
                        projectionOptions.styleApplyer(domNode, styleName, '');
                    }
                }
            } else {
                if (!propValue && typeof previousValue === 'string') {
                    propValue = '';
                }
                if (propName === 'value') {
                    if (domNode[propName] !== propValue && domNode['oninput-value'] !== propValue) {
                        domNode[propName] = propValue;
                        // Reset the value, even if the virtual DOM did not change
                        domNode['oninput-value'] = undefined;
                    }
                    // else do not update the domNode, otherwise the cursor position would be changed
                    if (propValue !== previousValue) {
                        propertiesUpdated = true;
                    }
                } else if (propValue !== previousValue) {
                    var type = typeof propValue;
                    if (type === 'function') {
                        throw new Error('Functions may not be updated on subsequent renders (property: ' + propName + '). Hint: declare event handler functions outside the render() function.');
                    }
                    if (type === 'string' && propName !== 'innerHTML') {
                        if (projectionOptions.namespace === NAMESPACE_SVG && propName === 'href') {
                            domNode.setAttributeNS(NAMESPACE_XLINK, propName, propValue);
                        } else {
                            domNode.setAttribute(propName, propValue);
                        }
                    } else {
                        if (domNode[propName] !== propValue) {
                            domNode[propName] = propValue;
                        }
                    }
                    propertiesUpdated = true;
                }
            }
        }
        return propertiesUpdated;
    };
    var findIndexOfChild = function (children, sameAs, start) {
        if (sameAs.vnodeSelector !== '') {
            // Never scan for text-nodes
            for (var i = start; i < children.length; i++) {
                if (same(children[i], sameAs)) {
                    return i;
                }
            }
        }
        return -1;
    };
    var nodeAdded = function (vNode, transitions) {
        if (vNode.properties) {
            var enterAnimation = vNode.properties.enterAnimation;
            if (enterAnimation) {
                if (typeof enterAnimation === 'function') {
                    enterAnimation(vNode.domNode, vNode.properties);
                } else {
                    transitions.enter(vNode.domNode, vNode.properties, enterAnimation);
                }
            }
        }
    };
    var nodeToRemove = function (vNode, transitions) {
        var domNode = vNode.domNode;
        if (vNode.properties) {
            var exitAnimation = vNode.properties.exitAnimation;
            if (exitAnimation) {
                domNode.style.pointerEvents = 'none';
                var removeDomNode = function () {
                    if (domNode.parentNode) {
                        domNode.parentNode.removeChild(domNode);
                    }
                };
                if (typeof exitAnimation === 'function') {
                    exitAnimation(domNode, removeDomNode, vNode.properties);
                    return;
                } else {
                    transitions.exit(vNode.domNode, vNode.properties, exitAnimation, removeDomNode);
                    return;
                }
            }
        }
        if (domNode.parentNode) {
            domNode.parentNode.removeChild(domNode);
        }
    };
    var checkDistinguishable = function (childNodes, indexToCheck, parentVNode, operation) {
        var childNode = childNodes[indexToCheck];
        if (childNode.vnodeSelector === '') {
            return;    // Text nodes need not be distinguishable
        }
        var properties = childNode.properties;
        var key = properties ? properties.key === undefined ? properties.bind : properties.key : undefined;
        if (!key) {
            for (var i = 0; i < childNodes.length; i++) {
                if (i !== indexToCheck) {
                    var node = childNodes[i];
                    if (same(node, childNode)) {
                        if (operation === 'added') {
                            throw new Error(parentVNode.vnodeSelector + ' had a ' + childNode.vnodeSelector + ' child ' + 'added, but there is now more than one. You must add unique key properties to make them distinguishable.');
                        } else {
                            throw new Error(parentVNode.vnodeSelector + ' had a ' + childNode.vnodeSelector + ' child ' + 'removed, but there were more than one. You must add unique key properties to make them distinguishable.');
                        }
                    }
                }
            }
        }
    };
    var createDom;
    var updateDom;
    var updateChildren = function (vnode, domNode, oldChildren, newChildren, projectionOptions) {
        if (oldChildren === newChildren) {
            return false;
        }
        oldChildren = oldChildren || emptyArray;
        newChildren = newChildren || emptyArray;
        var oldChildrenLength = oldChildren.length;
        var newChildrenLength = newChildren.length;
        var transitions = projectionOptions.transitions;
        var oldIndex = 0;
        var newIndex = 0;
        var i;
        var textUpdated = false;
        while (newIndex < newChildrenLength) {
            var oldChild = oldIndex < oldChildrenLength ? oldChildren[oldIndex] : undefined;
            var newChild = newChildren[newIndex];
            if (oldChild !== undefined && same(oldChild, newChild)) {
                textUpdated = updateDom(oldChild, newChild, projectionOptions) || textUpdated;
                oldIndex++;
            } else {
                var findOldIndex = findIndexOfChild(oldChildren, newChild, oldIndex + 1);
                if (findOldIndex >= 0) {
                    // Remove preceding missing children
                    for (i = oldIndex; i < findOldIndex; i++) {
                        nodeToRemove(oldChildren[i], transitions);
                        checkDistinguishable(oldChildren, i, vnode, 'removed');
                    }
                    textUpdated = updateDom(oldChildren[findOldIndex], newChild, projectionOptions) || textUpdated;
                    oldIndex = findOldIndex + 1;
                } else {
                    // New child
                    createDom(newChild, domNode, oldIndex < oldChildrenLength ? oldChildren[oldIndex].domNode : undefined, projectionOptions);
                    nodeAdded(newChild, transitions);
                    checkDistinguishable(newChildren, newIndex, vnode, 'added');
                }
            }
            newIndex++;
        }
        if (oldChildrenLength > oldIndex) {
            // Remove child fragments
            for (i = oldIndex; i < oldChildrenLength; i++) {
                nodeToRemove(oldChildren[i], transitions);
                checkDistinguishable(oldChildren, i, vnode, 'removed');
            }
        }
        return textUpdated;
    };
    var addChildren = function (domNode, children, projectionOptions) {
        if (!children) {
            return;
        }
        for (var i = 0; i < children.length; i++) {
            createDom(children[i], domNode, undefined, projectionOptions);
        }
    };
    var initPropertiesAndChildren = function (domNode, vnode, projectionOptions) {
        addChildren(domNode, vnode.children, projectionOptions);
        // children before properties, needed for value property of <select>.
        if (vnode.text) {
            domNode.textContent = vnode.text;
        }
        setProperties(domNode, vnode.properties, projectionOptions);
        if (vnode.properties && vnode.properties.afterCreate) {
            vnode.properties.afterCreate(domNode, projectionOptions, vnode.vnodeSelector, vnode.properties, vnode.children);
        }
    };
    createDom = function (vnode, parentNode, insertBefore, projectionOptions) {
        var domNode, i, c, start = 0, type, found;
        var vnodeSelector = vnode.vnodeSelector;
        if (vnodeSelector === '') {
            domNode = vnode.domNode = document.createTextNode(vnode.text);
            if (insertBefore !== undefined) {
                parentNode.insertBefore(domNode, insertBefore);
            } else {
                parentNode.appendChild(domNode);
            }
        } else {
            for (i = 0; i <= vnodeSelector.length; ++i) {
                c = vnodeSelector.charAt(i);
                if (i === vnodeSelector.length || c === '.' || c === '#') {
                    type = vnodeSelector.charAt(start - 1);
                    found = vnodeSelector.slice(start, i);
                    if (type === '.') {
                        domNode.classList.add(found);
                    } else if (type === '#') {
                        domNode.id = found;
                    } else {
                        if (found === 'svg') {
                            projectionOptions = extend(projectionOptions, { namespace: NAMESPACE_SVG });
                        }
                        if (projectionOptions.namespace !== undefined) {
                            domNode = vnode.domNode = document.createElementNS(projectionOptions.namespace, found);
                        } else {
                            domNode = vnode.domNode = document.createElement(found);
                        }
                        if (insertBefore !== undefined) {
                            parentNode.insertBefore(domNode, insertBefore);
                        } else {
                            parentNode.appendChild(domNode);
                        }
                    }
                    start = i + 1;
                }
            }
            initPropertiesAndChildren(domNode, vnode, projectionOptions);
        }
    };
    updateDom = function (previous, vnode, projectionOptions) {
        var domNode = previous.domNode;
        var textUpdated = false;
        if (previous === vnode) {
            return false;    // By contract, VNode objects may not be modified anymore after passing them to maquette
        }
        var updated = false;
        if (vnode.vnodeSelector === '') {
            if (vnode.text !== previous.text) {
                var newVNode = document.createTextNode(vnode.text);
                domNode.parentNode.replaceChild(newVNode, domNode);
                vnode.domNode = newVNode;
                textUpdated = true;
                return textUpdated;
            }
        } else {
            if (vnode.vnodeSelector.lastIndexOf('svg', 0) === 0) {
                projectionOptions = extend(projectionOptions, { namespace: NAMESPACE_SVG });
            }
            if (previous.text !== vnode.text) {
                updated = true;
                if (vnode.text === undefined) {
                    domNode.removeChild(domNode.firstChild);    // the only textnode presumably
                } else {
                    domNode.textContent = vnode.text;
                }
            }
            updated = updateChildren(vnode, domNode, previous.children, vnode.children, projectionOptions) || updated;
            updated = updateProperties(domNode, previous.properties, vnode.properties, projectionOptions) || updated;
            if (vnode.properties && vnode.properties.afterUpdate) {
                vnode.properties.afterUpdate(domNode, projectionOptions, vnode.vnodeSelector, vnode.properties, vnode.children);
            }
        }
        if (updated && vnode.properties && vnode.properties.updateAnimation) {
            vnode.properties.updateAnimation(domNode, vnode.properties, previous.properties);
        }
        vnode.domNode = previous.domNode;
        return textUpdated;
    };
    var createProjection = function (vnode, projectionOptions) {
        return {
            update: function (updatedVnode) {
                if (vnode.vnodeSelector !== updatedVnode.vnodeSelector) {
                    throw new Error('The selector for the root VNode may not be changed. (consider using dom.merge and add one extra level to the virtual DOM)');
                }
                updateDom(vnode, updatedVnode, projectionOptions);
                vnode = updatedVnode;
            },
            domNode: vnode.domNode
        };
    };
    ;
    // The other two parameters are not added here, because the Typescript compiler creates surrogate code for desctructuring 'children'.
    exports.h = function (selector) {
        var properties = arguments[1];
        if (typeof selector !== 'string') {
            throw new Error();
        }
        var childIndex = 1;
        if (properties && !properties.hasOwnProperty('vnodeSelector') && !Array.isArray(properties) && typeof properties === 'object') {
            childIndex = 2;
        } else {
            // Optional properties argument was omitted
            properties = undefined;
        }
        var text = undefined;
        var children = undefined;
        var argsLength = arguments.length;
        // Recognize a common special case where there is only a single text node
        if (argsLength === childIndex + 1) {
            var onlyChild = arguments[childIndex];
            if (typeof onlyChild === 'string') {
                text = onlyChild;
            } else if (onlyChild !== undefined && onlyChild.length === 1 && typeof onlyChild[0] === 'string') {
                text = onlyChild[0];
            }
        }
        if (text === undefined) {
            children = [];
            for (; childIndex < arguments.length; childIndex++) {
                var child = arguments[childIndex];
                if (child === null || child === undefined) {
                    continue;
                } else if (Array.isArray(child)) {
                    appendChildren(selector, child, children);
                } else if (child.hasOwnProperty('vnodeSelector')) {
                    children.push(child);
                } else {
                    children.push(toTextVNode(child));
                }
            }
        }
        return {
            vnodeSelector: selector,
            properties: properties,
            children: children,
            text: text === '' ? undefined : text,
            domNode: null
        };
    };
    /**
 * Contains simple low-level utility functions to manipulate the real DOM.
 */
    exports.dom = {
        /**
     * Creates a real DOM tree from `vnode`. The [[Projection]] object returned will contain the resulting DOM Node in
     * its [[Projection.domNode|domNode]] property.
     * This is a low-level method. Users wil typically use a [[Projector]] instead.
     * @param vnode - The root of the virtual DOM tree that was created using the [[h]] function. NOTE: [[VNode]]
     * objects may only be rendered once.
     * @param projectionOptions - Options to be used to create and update the projection.
     * @returns The [[Projection]] which also contains the DOM Node that was created.
     */
        create: function (vnode, projectionOptions) {
            projectionOptions = applyDefaultProjectionOptions(projectionOptions);
            createDom(vnode, document.createElement('div'), undefined, projectionOptions);
            return createProjection(vnode, projectionOptions);
        },
        /**
     * Appends a new childnode to the DOM which is generated from a [[VNode]].
     * This is a low-level method. Users wil typically use a [[Projector]] instead.
     * @param parentNode - The parent node for the new childNode.
     * @param vnode - The root of the virtual DOM tree that was created using the [[h]] function. NOTE: [[VNode]]
     * objects may only be rendered once.
     * @param projectionOptions - Options to be used to create and update the [[Projection]].
     * @returns The [[Projection]] that was created.
     */
        append: function (parentNode, vnode, projectionOptions) {
            projectionOptions = applyDefaultProjectionOptions(projectionOptions);
            createDom(vnode, parentNode, undefined, projectionOptions);
            return createProjection(vnode, projectionOptions);
        },
        /**
     * Inserts a new DOM node which is generated from a [[VNode]].
     * This is a low-level method. Users wil typically use a [[Projector]] instead.
     * @param beforeNode - The node that the DOM Node is inserted before.
     * @param vnode - The root of the virtual DOM tree that was created using the [[h]] function.
     * NOTE: [[VNode]] objects may only be rendered once.
     * @param projectionOptions - Options to be used to create and update the projection, see [[createProjector]].
     * @returns The [[Projection]] that was created.
     */
        insertBefore: function (beforeNode, vnode, projectionOptions) {
            projectionOptions = applyDefaultProjectionOptions(projectionOptions);
            createDom(vnode, beforeNode.parentNode, beforeNode, projectionOptions);
            return createProjection(vnode, projectionOptions);
        },
        /**
     * Merges a new DOM node which is generated from a [[VNode]] with an existing DOM Node.
     * This means that the virtual DOM and the real DOM will have one overlapping element.
     * Therefore the selector for the root [[VNode]] will be ignored, but its properties and children will be applied to the Element provided.
     * This is a low-level method. Users wil typically use a [[Projector]] instead.
     * @param domNode - The existing element to adopt as the root of the new virtual DOM. Existing attributes and childnodes are preserved.
     * @param vnode - The root of the virtual DOM tree that was created using the [[h]] function. NOTE: [[VNode]] objects
     * may only be rendered once.
     * @param projectionOptions - Options to be used to create and update the projection, see [[createProjector]].
     * @returns The [[Projection]] that was created.
     */
        merge: function (element, vnode, projectionOptions) {
            projectionOptions = applyDefaultProjectionOptions(projectionOptions);
            vnode.domNode = element;
            initPropertiesAndChildren(element, vnode, projectionOptions);
            return createProjection(vnode, projectionOptions);
        }
    };
    /**
 * Creates a [[CalculationCache]] object, useful for caching [[VNode]] trees.
 * In practice, caching of [[VNode]] trees is not needed, because achieving 60 frames per second is almost never a problem.
 * For more information, see [[CalculationCache]].
 *
 * @param <Result> The type of the value that is cached.
 */
    exports.createCache = function () {
        var cachedInputs = undefined;
        var cachedOutcome = undefined;
        var result = {
            invalidate: function () {
                cachedOutcome = undefined;
                cachedInputs = undefined;
            },
            result: function (inputs, calculation) {
                if (cachedInputs) {
                    for (var i = 0; i < inputs.length; i++) {
                        if (cachedInputs[i] !== inputs[i]) {
                            cachedOutcome = undefined;
                        }
                    }
                }
                if (!cachedOutcome) {
                    cachedOutcome = calculation();
                    cachedInputs = inputs;
                }
                return cachedOutcome;
            }
        };
        return result;
    };
    /**
 * Creates a {@link Mapping} instance that keeps an array of result objects synchronized with an array of source objects.
 * See {@link http://maquettejs.org/docs/arrays.html|Working with arrays}.
 *
 * @param <Source>       The type of source items. A database-record for instance.
 * @param <Target>       The type of target items. A [[Component]] for instance.
 * @param getSourceKey   `function(source)` that must return a key to identify each source object. The result must either be a string or a number.
 * @param createResult   `function(source, index)` that must create a new result object from a given source. This function is identical
 *                       to the `callback` argument in `Array.map(callback)`.
 * @param updateResult   `function(source, target, index)` that updates a result to an updated source.
 */
    exports.createMapping = function (getSourceKey, createResult, updateResult) {
        var keys = [];
        var results = [];
        return {
            results: results,
            map: function (newSources) {
                var newKeys = newSources.map(getSourceKey);
                var oldTargets = results.slice();
                var oldIndex = 0;
                for (var i = 0; i < newSources.length; i++) {
                    var source = newSources[i];
                    var sourceKey = newKeys[i];
                    if (sourceKey === keys[oldIndex]) {
                        results[i] = oldTargets[oldIndex];
                        updateResult(source, oldTargets[oldIndex], i);
                        oldIndex++;
                    } else {
                        var found = false;
                        for (var j = 1; j < keys.length; j++) {
                            var searchIndex = (oldIndex + j) % keys.length;
                            if (keys[searchIndex] === sourceKey) {
                                results[i] = oldTargets[searchIndex];
                                updateResult(newSources[i], oldTargets[searchIndex], i);
                                oldIndex = searchIndex + 1;
                                found = true;
                                break;
                            }
                        }
                        if (!found) {
                            results[i] = createResult(source, i);
                        }
                    }
                }
                results.length = newSources.length;
                keys = newKeys;
            }
        };
    };
    /**
 * Creates a [[Projector]] instance using the provided projectionOptions.
 *
 * For more information, see [[Projector]].
 *
 * @param projectionOptions   Options that influence how the DOM is rendered and updated.
 */
    exports.createProjector = function (projectorOptions) {
        var projector;
        var projectionOptions = applyDefaultProjectionOptions(projectorOptions);
        projectionOptions.eventHandlerInterceptor = function (propertyName, eventHandler, domNode, properties) {
            return function () {
                // intercept function calls (event handlers) to do a render afterwards.
                projector.scheduleRender();
                return eventHandler.apply(properties.bind || this, arguments);
            };
        };
        var renderCompleted = true;
        var scheduled;
        var stopped = false;
        var projections = [];
        var renderFunctions = [];
        // matches the projections array
        var doRender = function () {
            scheduled = undefined;
            if (!renderCompleted) {
                return;    // The last render threw an error, it should be logged in the browser console.
            }
            renderCompleted = false;
            for (var i = 0; i < projections.length; i++) {
                var updatedVnode = renderFunctions[i]();
                projections[i].update(updatedVnode);
            }
            renderCompleted = true;
        };
        projector = {
            scheduleRender: function () {
                if (!scheduled && !stopped) {
                    scheduled = requestAnimationFrame(doRender);
                }
            },
            stop: function () {
                if (scheduled) {
                    cancelAnimationFrame(scheduled);
                    scheduled = undefined;
                }
                stopped = true;
            },
            resume: function () {
                stopped = false;
                renderCompleted = true;
                projector.scheduleRender();
            },
            append: function (parentNode, renderMaquetteFunction) {
                projections.push(exports.dom.append(parentNode, renderMaquetteFunction(), projectionOptions));
                renderFunctions.push(renderMaquetteFunction);
            },
            insertBefore: function (beforeNode, renderMaquetteFunction) {
                projections.push(exports.dom.insertBefore(beforeNode, renderMaquetteFunction(), projectionOptions));
                renderFunctions.push(renderMaquetteFunction);
            },
            merge: function (domNode, renderMaquetteFunction) {
                projections.push(exports.dom.merge(domNode, renderMaquetteFunction(), projectionOptions));
                renderFunctions.push(renderMaquetteFunction);
            },
            replace: function (domNode, renderMaquetteFunction) {
                var vnode = renderMaquetteFunction();
                createDom(vnode, domNode.parentNode, domNode, projectionOptions);
                domNode.parentNode.removeChild(domNode);
                projections.push(createProjection(vnode, projectionOptions));
                renderFunctions.push(renderMaquetteFunction);
            },
            detach: function (renderMaquetteFunction) {
                for (var i = 0; i < renderFunctions.length; i++) {
                    if (renderFunctions[i] === renderMaquetteFunction) {
                        renderFunctions.splice(i, 1);
                        return projections.splice(i, 1)[0];
                    }
                }
                throw new Error('renderMaquetteFunction was not found');
            }
        };
        return projector;
    };
}));


/* ---- FileEditor.coffee ---- */


(function() {
  var FileEditor,
    bind = function(fn, me){ return function(){ return fn.apply(me, arguments); }; },
    extend = function(child, parent) { for (var key in parent) { if (hasProp.call(parent, key)) child[key] = parent[key]; } function ctor() { this.constructor = child; } ctor.prototype = parent.prototype; child.prototype = new ctor(); child.__super__ = parent.prototype; return child; },
    hasProp = {}.hasOwnProperty;

  FileEditor = (function(superClass) {
    extend(FileEditor, superClass);

    function FileEditor(inner_path1) {
      this.inner_path = inner_path1;
      this.save = bind(this.save, this);
      this.handleSaveClick = bind(this.handleSaveClick, this);
      this.handleSidebarButtonClick = bind(this.handleSidebarButtonClick, this);
      this.foldJson = bind(this.foldJson, this);
      this.storeCmNode = bind(this.storeCmNode, this);
      this.isModified = bind(this.isModified, this);
      this.need_update = true;
      this.on_loaded = new Promise();
      this.is_loading = false;
      this.content = "";
      this.node_cm = null;
      this.cm = null;
      this.error = null;
      this.is_loaded = false;
      this.is_modified = false;
      this.is_saving = false;
      this.mode = "Loading";
    }

    FileEditor.prototype.update = function() {
      var is_required;
      is_required = Page.url_params.get("edit_mode") !== "new";
      return Page.cmd("fileGet", {
        inner_path: this.inner_path,
        required: is_required
      }, (function(_this) {
        return function(res) {
          if (res != null ? res.error : void 0) {
            _this.error = res.error;
            _this.content = res.error;
            _this.log("Error loading: " + _this.error);
          } else {
            if (res) {
              _this.content = res;
            } else {
              _this.content = "";
              _this.mode = "Create";
            }
          }
          if (!_this.content) {
            _this.cm.getDoc().clearHistory();
          }
          _this.cm.setValue(_this.content);
          if (!_this.error) {
            _this.is_loaded = true;
          }
          return Page.projector.scheduleRender();
        };
      })(this));
    };

    FileEditor.prototype.isModified = function() {
      return this.content !== this.cm.getValue();
    };

    FileEditor.prototype.storeCmNode = function(node) {
      return this.node_cm = node;
    };

    FileEditor.prototype.getMode = function(inner_path) {
      var ext, types;
      ext = inner_path.split(".").pop();
      types = {
        "py": "python",
        "json": "application/json",
        "js": "javascript",
        "coffee": "coffeescript",
        "html": "htmlmixed",
        "htm": "htmlmixed",
        "php": "htmlmixed",
        "rs": "rust",
        "css": "css",
        "md": "markdown",
        "xml": "xml",
        "svg": "xml"
      };
      return types[ext];
    };

    FileEditor.prototype.foldJson = function(from, to) {
      var count, e, endToken, internal, parsed, prevLine, startToken, toParse;
      this.log("foldJson", from, to);
      startToken = '{';
      endToken = '}';
      prevLine = this.cm.getLine(from.line);
      if (prevLine.lastIndexOf('[') > prevLine.lastIndexOf('{')) {
        startToken = '[';
        endToken = ']';
      }
      internal = this.cm.getRange(from, to);
      toParse = startToken + internal + endToken;
      try {
        parsed = JSON.parse(toParse);
        count = Object.keys(parsed).length;
      } catch (error) {
        e = error;
        null;
      }
      if (count) {
        return "\u21A4" + count + "\u21A6";
      } else {
        return "\u2194";
      }
    };

    FileEditor.prototype.createCodeMirror = function() {
      var mode, options;
      mode = this.getMode(this.inner_path);
      this.log("Creating CodeMirror", this.inner_path, mode);
      options = {
        value: "Loading...",
        mode: mode,
        lineNumbers: true,
        styleActiveLine: true,
        matchBrackets: true,
        keyMap: "sublime",
        theme: "mdn-like",
        extraKeys: {
          "Ctrl-Space": "autocomplete"
        },
        foldGutter: true,
        gutters: ["CodeMirror-linenumbers", "CodeMirror-foldgutter"]
      };
      if (mode === "application/json") {
        options.gutters.unshift("CodeMirror-lint-markers");
        options.lint = true;
        options.foldOptions = {
          widget: this.foldJson
        };
      }
      this.cm = CodeMirror(this.node_cm, options);
      return this.cm.on("changes", (function(_this) {
        return function(changes) {
          if (_this.is_loaded && !_this.is_modified) {
            _this.is_modified = true;
            return Page.projector.scheduleRender();
          }
        };
      })(this));
    };

    FileEditor.prototype.loadEditor = function() {
      var script;
      if (!this.is_loading) {
        document.getElementsByTagName("head")[0].insertAdjacentHTML("beforeend", "<link rel=\"stylesheet\" href=\"codemirror/all.css\" />");
        script = document.createElement('script');
        script.src = "codemirror/all.js";
        script.onload = (function(_this) {
          return function() {
            _this.createCodeMirror();
            return _this.on_loaded.resolve();
          };
        })(this);
        document.head.appendChild(script);
      }
      return this.on_loaded;
    };

    FileEditor.prototype.handleSidebarButtonClick = function() {
      Page.is_sidebar_closed = !Page.is_sidebar_closed;
      return false;
    };

    FileEditor.prototype.handleSaveClick = function() {
      var mark, num_errors;
      num_errors = ((function() {
        var i, len, ref, results;
        ref = Page.file_editor.cm.getAllMarks();
        results = [];
        for (i = 0, len = ref.length; i < len; i++) {
          mark = ref[i];
          if (mark.className === "CodeMirror-lint-mark-error") {
            results.push(mark);
          }
        }
        return results;
      })()).length;
      if (num_errors > 0) {
        Page.cmd("wrapperConfirm", ["<b>Warning:</b> The file looks invalid.", "Save anyway"], this.save);
      } else {
        this.save();
      }
      return false;
    };

    FileEditor.prototype.save = function() {
      Page.projector.scheduleRender();
      this.is_saving = true;
      return Page.cmd("fileWrite", [this.inner_path, Text.fileEncode(this.cm.getValue())], (function(_this) {
        return function(res) {
          _this.is_saving = false;
          if (res.error) {
            Page.cmd("wrapperNotification", ["error", "Error saving " + res.error]);
          } else {
            _this.is_save_done = true;
            setTimeout((function() {
              _this.is_save_done = false;
              return Page.projector.scheduleRender();
            }), 2000);
            _this.content = _this.cm.getValue();
            _this.is_modified = false;
            if (_this.mode === "Create") {
              _this.mode = "Edit";
            }
            Page.file_list.need_update = true;
          }
          return Page.projector.scheduleRender();
        };
      })(this));
    };

    FileEditor.prototype.render = function() {
      var ref;
      if (this.need_update) {
        this.loadEditor().then((function(_this) {
          return function() {
            return _this.update();
          };
        })(this));
        this.need_update = false;
      }
      return h("div.editor", {
        afterCreate: this.storeCmNode,
        classes: {
          error: this.error,
          loaded: this.is_loaded
        }
      }, [
        h("a.sidebar-button", {
          href: "#Sidebar",
          onclick: this.handleSidebarButtonClick
        }, h("span", "\u2039")), h("div.editor-head", [
          (ref = this.mode) === "Edit" || ref === "Create" ? h("a.save.button", {
            href: "#Save",
            classes: {
              loading: this.is_saving,
              done: this.is_save_done,
              disabled: !this.is_modified
            },
            onclick: this.handleSaveClick
          }, this.is_save_done ? "Save: done!" : "Save") : void 0, h("span.title", this.mode, ": ", this.inner_path)
        ]), this.error ? h("div.error-message", h("h2", "Unable to load the file: " + this.error), h("a", {
          href: Page.file_list.getHref(this.inner_path)
        }, "View in browser")) : void 0
      ]);
    };

    return FileEditor;

  })(Class);

  window.FileEditor = FileEditor;

}).call(this);


/* ---- FileItemList.coffee ---- */


(function() {
  var FileItemList,
    bind = function(fn, me){ return function(){ return fn.apply(me, arguments); }; },
    extend = function(child, parent) { for (var key in parent) { if (hasProp.call(parent, key)) child[key] = parent[key]; } function ctor() { this.constructor = child; } ctor.prototype = parent.prototype; child.prototype = new ctor(); child.__super__ = parent.prototype; return child; },
    hasProp = {}.hasOwnProperty;

  FileItemList = (function(superClass) {
    extend(FileItemList, superClass);

    function FileItemList(inner_path1) {
      this.inner_path = inner_path1;
      this.sort = bind(this.sort, this);
      this.getOptionalInfo = bind(this.getOptionalInfo, this);
      this.hasPermissionDelete = bind(this.hasPermissionDelete, this);
      this.isAdded = bind(this.isAdded, this);
      this.isModified = bind(this.isModified, this);
      this.getFileType = bind(this.getFileType, this);
      this.addOptionalFilesToItems = bind(this.addOptionalFilesToItems, this);
      this.updateOptionalFiles = bind(this.updateOptionalFiles, this);
      this.updateAddedFiles = bind(this.updateAddedFiles, this);
      this.updateModifiedFiles = bind(this.updateModifiedFiles, this);
      this.items = [];
      this.updating = false;
      this.files_modified = {};
      this.dirs_modified = {};
      this.files_added = {};
      this.dirs_added = {};
      this.files_optional = {};
      this.items_by_name = {};
    }

    FileItemList.prototype.update = function(cb) {
      this.updating = true;
      this.logStart("Updating dirlist");
      return Page.cmd("dirList", {
        inner_path: this.inner_path,
        stats: true
      }, (function(_this) {
        return function(res) {
          var i, len, pattern_ignore, ref, ref1, ref2, ref3, row;
          if (res.error) {
            _this.error = res.error;
          } else {
            _this.error = null;
            pattern_ignore = RegExp("^" + ((ref = Page.site_info.content) != null ? ref.ignore : void 0));
            _this.items.splice(0, _this.items.length);
            _this.items_by_name = {};
            for (i = 0, len = res.length; i < len; i++) {
              row = res[i];
              row.type = _this.getFileType(row);
              row.inner_path = _this.inner_path + row.name;
              if (((ref1 = Page.site_info.content) != null ? ref1.ignore : void 0) && row.inner_path.match(pattern_ignore)) {
                row.ignored = true;
              }
              _this.items.push(row);
              _this.items_by_name[row.name] = row;
            }
            _this.sort();
          }
          if ((ref2 = Page.site_info) != null ? (ref3 = ref2.settings) != null ? ref3.own : void 0 : void 0) {
            _this.updateAddedFiles();
          }
          return _this.updateOptionalFiles(function() {
            _this.updating = false;
            if (typeof cb === "function") {
              cb();
            }
            _this.logEnd("Updating dirlist", _this.inner_path);
            Page.projector.scheduleRender();
            return _this.updateModifiedFiles(function() {
              return Page.projector.scheduleRender();
            });
          });
        };
      })(this));
    };

    FileItemList.prototype.updateModifiedFiles = function(cb) {
      return Page.cmd("siteListModifiedFiles", [], (function(_this) {
        return function(res) {
          var dir_inner_path, dir_part, dir_parts, i, inner_path, j, len, len1, ref, ref1;
          _this.files_modified = {};
          _this.dirs_modified = {};
          ref = res.modified_files;
          for (i = 0, len = ref.length; i < len; i++) {
            inner_path = ref[i];
            _this.files_modified[inner_path] = true;
            dir_inner_path = "";
            dir_parts = inner_path.split("/");
            ref1 = dir_parts.slice(0, -1);
            for (j = 0, len1 = ref1.length; j < len1; j++) {
              dir_part = ref1[j];
              if (dir_inner_path) {
                dir_inner_path += "/" + dir_part;
              } else {
                dir_inner_path = dir_part;
              }
              _this.dirs_modified[dir_inner_path] = true;
            }
          }
          return typeof cb === "function" ? cb() : void 0;
        };
      })(this));
    };

    FileItemList.prototype.updateAddedFiles = function() {
      return Page.cmd("fileGet", "content.json", (function(_this) {
        return function(res) {
          var content, dirs_content, file, file_name, i, j, len, len1, match, pattern, ref, ref1, results;
          if (!res) {
            return false;
          }
          content = JSON.parse(res);
          if (content.files == null) {
            return false;
          }
          _this.files_added = {};
          ref = _this.items;
          for (i = 0, len = ref.length; i < len; i++) {
            file = ref[i];
            if (file.name === "content.json" || file.is_dir) {
              continue;
            }
            if (!content.files[_this.inner_path + file.name]) {
              _this.files_added[_this.inner_path + file.name] = true;
            }
          }
          _this.dirs_added = {};
          dirs_content = {};
          for (file_name in Object.assign({}, content.files, content.files_optional)) {
            if (!file_name.startsWith(_this.inner_path)) {
              continue;
            }
            pattern = new RegExp(_this.inner_path + "(.*?)/");
            match = file_name.match(pattern);
            if (!match) {
              continue;
            }
            dirs_content[match[1]] = true;
          }
          ref1 = _this.items;
          results = [];
          for (j = 0, len1 = ref1.length; j < len1; j++) {
            file = ref1[j];
            if (!file.is_dir) {
              continue;
            }
            if (!dirs_content[file.name]) {
              results.push(_this.dirs_added[_this.inner_path + file.name] = true);
            } else {
              results.push(void 0);
            }
          }
          return results;
        };
      })(this));
    };

    FileItemList.prototype.updateOptionalFiles = function(cb) {
      return Page.cmd("optionalFileList", {
        filter: ""
      }, (function(_this) {
        return function(res) {
          var i, len, optional_file;
          _this.files_optional = {};
          for (i = 0, len = res.length; i < len; i++) {
            optional_file = res[i];
            _this.files_optional[optional_file.inner_path] = optional_file;
          }
          _this.addOptionalFilesToItems();
          return typeof cb === "function" ? cb() : void 0;
        };
      })(this));
    };

    FileItemList.prototype.addOptionalFilesToItems = function() {
      var dir_name, file_name, inner_path, is_added, optional_file, ref, ref1, row;
      is_added = false;
      ref = this.files_optional;
      for (inner_path in ref) {
        optional_file = ref[inner_path];
        if (optional_file.inner_path.startsWith(this.inner_path)) {
          if (this.getDirectory(optional_file.inner_path) === this.inner_path) {
            file_name = this.getFileName(optional_file.inner_path);
            if (!this.items_by_name[file_name]) {
              row = {
                "name": file_name,
                "type": "file",
                "optional_empty": true,
                "size": optional_file.size,
                "is_dir": false,
                "inner_path": optional_file.inner_path
              };
              this.items.push(row);
              this.items_by_name[file_name] = row;
              is_added = true;
            }
          } else {
            dir_name = (ref1 = optional_file.inner_path.replace(this.inner_path, "").match(/(.*?)\//, "")) != null ? ref1[1] : void 0;
            if (dir_name && !this.items_by_name[dir_name]) {
              row = {
                "name": dir_name,
                "type": "dir",
                "optional_empty": true,
                "size": 0,
                "is_dir": true,
                "inner_path": optional_file.inner_path
              };
              this.items.push(row);
              this.items_by_name[dir_name] = row;
              is_added = true;
            }
          }
        }
      }
      if (is_added) {
        return this.sort();
      }
    };

    FileItemList.prototype.getFileType = function(file) {
      if (file.is_dir) {
        return "dir";
      } else {
        return "unknown";
      }
    };

    FileItemList.prototype.getDirectory = function(inner_path) {
      if (inner_path.indexOf("/") !== -1) {
        return inner_path.replace(/^(.*\/)(.*?)$/, "$1");
      } else {
        return "";
      }
    };

    FileItemList.prototype.getFileName = function(inner_path) {
      return inner_path.replace(/^(.*\/)(.*?)$/, "$2");
    };

    FileItemList.prototype.isModified = function(inner_path) {
      return this.files_modified[inner_path] || this.dirs_modified[inner_path];
    };

    FileItemList.prototype.isAdded = function(inner_path) {
      return this.files_added[inner_path] || this.dirs_added[inner_path];
    };

    FileItemList.prototype.hasPermissionDelete = function(file) {
      var optional_info, ref, ref1, ref2;
      if ((ref = file.type) === "dir" || ref === "parent") {
        return false;
      }
      if (file.inner_path === "content.json") {
        return false;
      }
      optional_info = this.getOptionalInfo(file.inner_path);
      if (optional_info && optional_info.downloaded_percent > 0) {
        return true;
      } else {
        return (ref1 = Page.site_info) != null ? (ref2 = ref1.settings) != null ? ref2.own : void 0 : void 0;
      }
    };

    FileItemList.prototype.getOptionalInfo = function(inner_path) {
      return this.files_optional[inner_path];
    };

    FileItemList.prototype.sort = function() {
      return this.items.sort(function(a, b) {
        return (b.is_dir - a.is_dir) || a.name.localeCompare(b.name);
      });
    };

    return FileItemList;

  })(Class);

  window.FileItemList = FileItemList;

}).call(this);

/* ---- FileList.coffee ---- */


(function() {
  var BINARY_EXTENSIONS, FileList,
    bind = function(fn, me){ return function(){ return fn.apply(me, arguments); }; },
    extend = function(child, parent) { for (var key in parent) { if (hasProp.call(parent, key)) child[key] = parent[key]; } function ctor() { this.constructor = child; } ctor.prototype = parent.prototype; child.prototype = new ctor(); child.__super__ = parent.prototype; return child; },
    hasProp = {}.hasOwnProperty,
    indexOf = [].indexOf || function(item) { for (var i = 0, l = this.length; i < l; i++) { if (i in this && this[i] === item) return i; } return -1; };

  BINARY_EXTENSIONS = ["png", "gif", "jpg", "pdf", "doc", "msgpack", "zip", "rar", "gz", "tar", "exe"];

  FileList = (function(superClass) {
    extend(FileList, superClass);

    function FileList(site, inner_path1, is_owner) {
      this.site = site;
      this.inner_path = inner_path1;
      this.is_owner = is_owner != null ? is_owner : false;
      this.render = bind(this.render, this);
      this.renderFoot = bind(this.renderFoot, this);
      this.renderItems = bind(this.renderItems, this);
      this.renderItem = bind(this.renderItem, this);
      this.renderItemCheckbox = bind(this.renderItemCheckbox, this);
      this.renderHead = bind(this.renderHead, this);
      this.renderSelectbar = bind(this.renderSelectbar, this);
      this.handleSelectbarRemoveOptional = bind(this.handleSelectbarRemoveOptional, this);
      this.handleSelectbarDelete = bind(this.handleSelectbarDelete, this);
      this.handleSelectbarCancel = bind(this.handleSelectbarCancel, this);
      this.handleRowMouseenter = bind(this.handleRowMouseenter, this);
      this.handleSelectMousedown = bind(this.handleSelectMousedown, this);
      this.handleSelectEnd = bind(this.handleSelectEnd, this);
      this.handleSelectClick = bind(this.handleSelectClick, this);
      this.handleNewDirectoryClick = bind(this.handleNewDirectoryClick, this);
      this.handleNewFileClick = bind(this.handleNewFileClick, this);
      this.handleMenuCreateClick = bind(this.handleMenuCreateClick, this);
      this.checkSelectedItems = bind(this.checkSelectedItems, this);
      this.getEditHref = bind(this.getEditHref, this);
      this.getListHref = bind(this.getListHref, this);
      this.getHref = bind(this.getHref, this);
      this.update = bind(this.update, this);
      this.need_update = true;
      this.error = null;
      this.url_root = "/list/" + this.site + "/";
      if (this.inner_path) {
        this.inner_path += "/";
        this.url_root += this.inner_path;
      }
      this.log("inited", this.url_root);
      this.item_list = new FileItemList(this.inner_path);
      this.item_list.items = this.item_list.items;
      this.menu_create = new Menu();
      this.select_action = null;
      this.selected = {};
      this.selected_items_num = 0;
      this.selected_items_size = 0;
      this.selected_optional_empty_num = 0;
    }

    FileList.prototype.isSelectedAll = function() {
      return false;
    };

    FileList.prototype.update = function() {
      return this.item_list.update((function(_this) {
        return function() {
          return document.body.classList.add("loaded");
        };
      })(this));
    };

    FileList.prototype.getHref = function(inner_path) {
      return "/" + this.site + "/" + inner_path;
    };

    FileList.prototype.getListHref = function(inner_path) {
      return "/list/" + this.site + "/" + inner_path;
    };

    FileList.prototype.getEditHref = function(inner_path, mode) {
      var href;
      if (mode == null) {
        mode = null;
      }
      href = this.url_root + "?file=" + inner_path;
      if (mode) {
        href += "&edit_mode=" + mode;
      }
      return href;
    };

    FileList.prototype.checkSelectedItems = function() {
      var i, item, len, optional_info, ref, results;
      this.selected_items_num = 0;
      this.selected_items_size = 0;
      this.selected_optional_empty_num = 0;
      ref = this.item_list.items;
      results = [];
      for (i = 0, len = ref.length; i < len; i++) {
        item = ref[i];
        if (this.selected[item.inner_path]) {
          this.selected_items_num += 1;
          this.selected_items_size += item.size;
          optional_info = this.item_list.getOptionalInfo(item.inner_path);
          if (optional_info && !optional_info.downloaded_percent > 0) {
            results.push(this.selected_optional_empty_num += 1);
          } else {
            results.push(void 0);
          }
        } else {
          results.push(void 0);
        }
      }
      return results;
    };

    FileList.prototype.handleMenuCreateClick = function() {
      this.menu_create.items = [];
      this.menu_create.items.push(["File", this.handleNewFileClick]);
      this.menu_create.items.push(["Directory", this.handleNewDirectoryClick]);
      this.menu_create.toggle();
      return false;
    };

    FileList.prototype.handleNewFileClick = function() {
      Page.cmd("wrapperPrompt", "New file name:", (function(_this) {
        return function(file_name) {
          return window.top.location.href = _this.getEditHref(_this.inner_path + file_name, "new");
        };
      })(this));
      return false;
    };

    FileList.prototype.handleNewDirectoryClick = function() {
      Page.cmd("wrapperPrompt", "New directory name:", (function(_this) {
        return function(res) {
          return alert("directory name " + res);
        };
      })(this));
      return false;
    };

    FileList.prototype.handleSelectClick = function(e) {
      return false;
    };

    FileList.prototype.handleSelectEnd = function(e) {
      document.body.removeEventListener('mouseup', this.handleSelectEnd);
      return this.select_action = null;
    };

    FileList.prototype.handleSelectMousedown = function(e) {
      var inner_path;
      inner_path = e.currentTarget.attributes.inner_path.value;
      if (this.selected[inner_path]) {
        delete this.selected[inner_path];
        this.select_action = "deselect";
      } else {
        this.selected[inner_path] = true;
        this.select_action = "select";
      }
      this.checkSelectedItems();
      document.body.addEventListener('mouseup', this.handleSelectEnd);
      e.stopPropagation();
      Page.projector.scheduleRender();
      return false;
    };

    FileList.prototype.handleRowMouseenter = function(e) {
      var inner_path;
      if (e.buttons && this.select_action) {
        inner_path = e.target.attributes.inner_path.value;
        if (this.select_action === "select") {
          this.selected[inner_path] = true;
        } else {
          delete this.selected[inner_path];
        }
        this.checkSelectedItems();
        Page.projector.scheduleRender();
      }
      return false;
    };

    FileList.prototype.handleSelectbarCancel = function() {
      this.selected = {};
      this.checkSelectedItems();
      Page.projector.scheduleRender();
      return false;
    };

    FileList.prototype.handleSelectbarDelete = function(e, remove_optional) {
      var inner_path, optional_info;
      if (remove_optional == null) {
        remove_optional = false;
      }
      for (inner_path in this.selected) {
        optional_info = this.item_list.getOptionalInfo(inner_path);
        delete this.selected[inner_path];
        if (optional_info && !remove_optional) {
          Page.cmd("optionalFileDelete", inner_path);
        } else {
          Page.cmd("fileDelete", inner_path);
        }
      }
      this.need_update = true;
      Page.projector.scheduleRender();
      this.checkSelectedItems();
      return false;
    };

    FileList.prototype.handleSelectbarRemoveOptional = function(e) {
      return this.handleSelectbarDelete(e, true);
    };

    FileList.prototype.renderSelectbar = function() {
      return h("div.selectbar", {
        classes: {
          visible: this.selected_items_num > 0
        }
      }, [
        "Selected:", h("span.info", [h("span.num", this.selected_items_num + " files"), h("span.size", "(" + (Text.formatSize(this.selected_items_size)) + ")")]), h("div.actions", [
          this.selected_optional_empty_num > 0 ? h("a.action.delete.remove_optional", {
            href: "#",
            onclick: this.handleSelectbarRemoveOptional
          }, "Delete and remove optional") : h("a.action.delete", {
            href: "#",
            onclick: this.handleSelectbarDelete
          }, "Delete")
        ]), h("a.cancel.link", {
          href: "#",
          onclick: this.handleSelectbarCancel
        }, "Cancel")
      ]);
    };

    FileList.prototype.renderHead = function() {
      var i, inner_path_parent, len, parent_dir, parent_links, ref;
      parent_links = [];
      inner_path_parent = "";
      ref = this.inner_path.split("/");
      for (i = 0, len = ref.length; i < len; i++) {
        parent_dir = ref[i];
        if (!parent_dir) {
          continue;
        }
        if (inner_path_parent) {
          inner_path_parent += "/";
        }
        inner_path_parent += "" + parent_dir;
        parent_links.push([
          " / ", h("a", {
            href: this.getListHref(inner_path_parent)
          }, parent_dir)
        ]);
      }
      return h("div.tr.thead", h("div.td.full", h("a", {
        href: this.getListHref("")
      }, "root"), parent_links));
    };

    FileList.prototype.renderItemCheckbox = function(item) {
      if (!this.item_list.hasPermissionDelete(item)) {
        return [" "];
      }
      return h("a.checkbox-outer", {
        href: "#Select",
        onmousedown: this.handleSelectMousedown,
        onclick: this.handleSelectClick,
        inner_path: item.inner_path
      }, h("span.checkbox"));
    };

    FileList.prototype.renderItem = function(item) {
      var classes, downloaded_percent, ext, href, href_edit, inner_path, is_added, is_dir, is_editable, is_editing, is_modified, obj, optional_info, ref, ref1, style, title;
      if (item.type === "parent") {
        href = this.url_root.replace(/^(.*)\/.{2,255}?$/, "$1/");
      } else if (item.type === "dir") {
        href = this.url_root + item.name;
      } else {
        href = this.url_root.replace(/^\/list\//, "/") + item.name;
      }
      inner_path = this.inner_path + item.name;
      href_edit = this.getEditHref(inner_path);
      is_dir = (ref = item.type) === "dir" || ref === "parent";
      ext = item.name.split(".").pop();
      is_editing = inner_path === ((ref1 = Page.file_editor) != null ? ref1.inner_path : void 0);
      is_editable = !is_dir && item.size < 1024 * 1024 && indexOf.call(BINARY_EXTENSIONS, ext) < 0;
      is_modified = this.item_list.isModified(inner_path);
      is_added = this.item_list.isAdded(inner_path);
      optional_info = this.item_list.getOptionalInfo(inner_path);
      style = "";
      title = "";
      if (optional_info) {
        downloaded_percent = optional_info.downloaded_percent;
        if (!downloaded_percent) {
          downloaded_percent = 0;
        }
        style += "background: linear-gradient(90deg, #fff6dd, " + downloaded_percent + "%, white, " + downloaded_percent + "%, white);";
        is_added = false;
      }
      if (item.ignored) {
        is_added = false;
      }
      if (is_modified) {
        title += " (modified)";
      }
      if (is_added) {
        title += " (new)";
      }
      if (optional_info || item.optional_empty) {
        title += " (optional)";
      }
      if (item.ignored) {
        title += " (ignored from content.json)";
      }
      classes = (
        obj = {},
        obj["type-" + item.type] = true,
        obj.editing = is_editing,
        obj.nobuttons = !is_editable,
        obj.selected = this.selected[inner_path],
        obj.modified = is_modified,
        obj.added = is_added,
        obj.ignored = item.ignored,
        obj.optional = optional_info,
        obj.optional_empty = item.optional_empty,
        obj
      );
      return h("div.tr", {
        key: item.name,
        classes: classes,
        style: style,
        onmouseenter: this.handleRowMouseenter,
        inner_path: inner_path
      }, [
        h("div.td.pre", {
          title: title
        }, this.renderItemCheckbox(item)), h("div.td.name", h("a.link", {
          href: href
        }, item.name)), h("div.td.buttons", is_editable ? h("a.edit", {
          href: href_edit
        }, Page.site_info.settings.own ? "Edit" : "View") : void 0), h("div.td.size", is_dir ? "[DIR]" : Text.formatSize(item.size))
      ]);
    };

    FileList.prototype.renderItems = function() {
      return [
        this.item_list.error && !this.item_list.items.length && !this.item_list.updating ? [
          h("div.tr", {
            key: "error"
          }, h("div.td.full.error", this.item_list.error))
        ] : void 0, this.inner_path ? this.renderItem({
          "name": "..",
          type: "parent",
          size: 0
        }) : void 0, this.item_list.items.map(this.renderItem)
      ];
    };

    FileList.prototype.renderFoot = function() {
      var dirs, file, files, foot_text, item, ref, ref1, ref2, ref3, total_size;
      files = (function() {
        var i, len, ref, ref1, results;
        ref = this.item_list.items;
        results = [];
        for (i = 0, len = ref.length; i < len; i++) {
          item = ref[i];
          if ((ref1 = item.type) !== "parent" && ref1 !== "dir") {
            results.push(item);
          }
        }
        return results;
      }).call(this);
      dirs = (function() {
        var i, len, ref, results;
        ref = this.item_list.items;
        results = [];
        for (i = 0, len = ref.length; i < len; i++) {
          item = ref[i];
          if (item.type === "dir") {
            results.push(item);
          }
        }
        return results;
      }).call(this);
      if (files.length) {
        total_size = ((function() {
          var i, len, results;
          results = [];
          for (i = 0, len = files.length; i < len; i++) {
            file = files[i];
            results.push(item.size);
          }
          return results;
        })()).reduce(function(a, b) {
          return a + b;
        });
      } else {
        total_size = 0;
      }
      foot_text = "Total: ";
      foot_text += dirs.length + " dir, " + files.length + " file in " + (Text.formatSize(total_size));
      return [
        dirs.length || files.length || ((ref = Page.site_info) != null ? (ref1 = ref.settings) != null ? ref1.own : void 0 : void 0) ? h("div.tr.foot-info.foot", h("div.td.full", [
          this.item_list.updating ? "Updating file list..." : dirs.length || files.length ? foot_text : void 0, ((ref2 = Page.site_info) != null ? (ref3 = ref2.settings) != null ? ref3.own : void 0 : void 0) ? h("div.create", [
            h("a.link", {
              href: "#Create+new+file",
              onclick: this.handleNewFileClick
            }, "+ New"), this.menu_create.render()
          ]) : void 0
        ])) : void 0
      ];
    };

    FileList.prototype.render = function() {
      if (this.need_update) {
        this.update();
        this.need_update = false;
        if (!this.item_list.items) {
          return [];
        }
      }
      return h("div.files", [this.renderSelectbar(), this.renderHead(), h("div.tbody", this.renderItems()), this.renderFoot()]);
    };

    return FileList;

  })(Class);

  window.FileList = FileList;

}).call(this);

/* ---- UiFileManager.coffee ---- */


(function() {
  var UiFileManager,
    bind = function(fn, me){ return function(){ return fn.apply(me, arguments); }; },
    extend = function(child, parent) { for (var key in parent) { if (hasProp.call(parent, key)) child[key] = parent[key]; } function ctor() { this.constructor = child; } ctor.prototype = parent.prototype; child.prototype = new ctor(); child.__super__ = parent.prototype; return child; },
    hasProp = {}.hasOwnProperty;

  window.h = maquette.h;

  UiFileManager = (function(superClass) {
    extend(UiFileManager, superClass);

    function UiFileManager() {
      this.render = bind(this.render, this);
      this.createProjector = bind(this.createProjector, this);
      this.onRequest = bind(this.onRequest, this);
      this.checkBodyWidth = bind(this.checkBodyWidth, this);
      return UiFileManager.__super__.constructor.apply(this, arguments);
    }

    UiFileManager.prototype.init = function() {
      this.url_params = new URLSearchParams(window.location.search);
      this.list_site = this.url_params.get("site");
      this.list_address = this.url_params.get("address");
      this.list_inner_path = this.url_params.get("inner_path");
      this.editor_inner_path = this.url_params.get("file");
      this.file_list = new FileList(this.list_site, this.list_inner_path);
      this.site_info = null;
      this.server_info = null;
      this.is_sidebar_closed = false;
      if (this.editor_inner_path) {
        this.file_editor = new FileEditor(this.editor_inner_path);
      }
      window.onbeforeunload = (function(_this) {
        return function() {
          var ref;
          if ((ref = _this.file_editor) != null ? ref.isModified() : void 0) {
            return true;
          } else {
            return null;
          }
        };
      })(this);
      window.onresize = (function(_this) {
        return function() {
          return _this.checkBodyWidth();
        };
      })(this);
      this.checkBodyWidth();
      this.cmd("wrapperSetViewport", "width=device-width, initial-scale=0.8");
      this.cmd("serverInfo", {}, (function(_this) {
        return function(server_info) {
          return _this.server_info = server_info;
        };
      })(this));
      return this.cmd("siteInfo", {}, (function(_this) {
        return function(site_info) {
          _this.cmd("wrapperSetTitle", "List: /" + _this.list_inner_path + " - " + site_info.content.title + " - ZeroNet");
          _this.site_info = site_info;
          if (_this.file_editor) {
            _this.file_editor.on_loaded.then(function() {
              _this.file_editor.cm.setOption("readOnly", !site_info.settings.own);
              return _this.file_editor.mode = site_info.settings.own ? "Edit" : "View";
            });
          }
          return _this.projector.scheduleRender();
        };
      })(this));
    };

    UiFileManager.prototype.checkBodyWidth = function() {
      var ref, ref1;
      if (!this.file_editor) {
        return false;
      }
      if (document.body.offsetWidth < 960 && !this.is_sidebar_closed) {
        this.is_sidebar_closed = true;
        return (ref = this.projector) != null ? ref.scheduleRender() : void 0;
      } else if (document.body.offsetWidth > 960 && this.is_sidebar_closed) {
        this.is_sidebar_closed = false;
        return (ref1 = this.projector) != null ? ref1.scheduleRender() : void 0;
      }
    };

    UiFileManager.prototype.onRequest = function(cmd, message) {
      if (cmd === "setSiteInfo") {
        this.site_info = message;
        RateLimitCb(1000, (function(_this) {
          return function(cb_done) {
            return _this.file_list.update(cb_done);
          };
        })(this));
        return this.projector.scheduleRender();
      } else if (cmd === "setServerInfo") {
        this.server_info = message;
        return this.projector.scheduleRender();
      } else {
        return this.log("Unknown incoming message:", cmd);
      }
    };

    UiFileManager.prototype.createProjector = function() {
      this.projector = maquette.createProjector();
      return this.projector.replace($("#content"), this.render);
    };

    UiFileManager.prototype.render = function() {
      return h("div.content#content", [
        h("div.manager", {
          classes: {
            editing: this.file_editor,
            sidebar_closed: this.is_sidebar_closed
          }
        }, [this.file_list.render(), this.file_editor ? this.file_editor.render() : void 0])
      ]);
    };

    return UiFileManager;

  })(ZeroFrame);

  window.Page = new UiFileManager();

  window.Page.createProjector();

}).call(this);