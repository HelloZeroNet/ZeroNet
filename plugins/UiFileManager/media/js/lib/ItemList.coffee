class ItemList
	constructor: (@item_class, @key) ->
		@items = []
		@items_bykey = {}

	sync: (rows, item_class, key) ->
		@items.splice(0, @items.length)  # Empty items
		for row in rows
			current_obj = @items_bykey[row[@key]]
			if current_obj
				current_obj.row = row
				@items.push current_obj
			else
				item = new @item_class(row, @)
				@items_bykey[row[@key]] = item
				@items.push item

	deleteItem: (item) ->
		index = @items.indexOf(item)
		if index > -1
			@items.splice(index, 1)
		else
			console.log "Can't delete item", item
		delete @items_bykey[item.row[@key]]

window.ItemList = ItemList