import re, time, cgi, os
from Plugin import PluginManager

@PluginManager.registerTo("UiRequest")
class UiRequestPlugin(object):
	def formatTableRow(self, row):
		back = []
		for format, val in row:
			if val == None: 
				formatted = "n/a"
			elif format == "since":
				if val:
					formatted = "%.0f" % (time.time()-val)
				else:
					formatted = "n/a"
			else:
				formatted = format % val
			back.append("<td>%s</td>" % formatted)
		return "<tr>%s</tr>" % "".join(back)


	def getObjSize(self, obj, hpy = None):
		if hpy:
			return float(hpy.iso(obj).domisize)/1024
		else:
			return 0


	# /Stats entry point
	def actionStats(self):
		import gc, sys
		from Ui import UiRequest
		
		hpy = None
		if self.get.get("size") == "1": # Calc obj size
			try:
				import guppy
				hpy = guppy.hpy()
			except:
				pass
		self.sendHeader()
		s = time.time()
		main = sys.modules["main"]

		# Style
		yield """
		<style>
		 * { font-family: monospace }
		 table * { text-align: right; padding: 0px 10px }
		</style>
		"""

		# Memory
		try:
			import psutil
			process = psutil.Process(os.getpid())
			mem = process.get_memory_info()[0] / float(2 ** 20)
			yield "Memory usage: %.2fMB | " % mem
			yield "Threads: %s | " % len(process.threads())
			yield "CPU: usr %.2fs sys %.2fs | " % process.cpu_times()
			yield "Open files: %s | " % len(process.open_files())
			yield "Sockets: %s" % len(process.connections())
			yield " | Calc size <a href='?size=1'>on</a> <a href='?size=0'>off</a><br>"
		except Exception, err:
			pass

		yield "Connections (%s):<br>" % len(main.file_server.connections)
		yield "<table><tr> <th>id</th> <th>protocol</th>  <th>type</th> <th>ip</th> <th>ping</th> <th>buff</th>"
		yield "<th>idle</th> <th>open</th> <th>delay</th> <th>sent</th> <th>received</th> <th>last sent</th> <th>waiting</th> <th>version</th> <th>peerid</th> </tr>"
		for connection in main.file_server.connections:
			yield self.formatTableRow([
				("%3d", connection.id),
				("%s", connection.protocol),
				("%s", connection.type),
				("%s", connection.ip),
				("%6.3f", connection.last_ping_delay),
				("%s", connection.incomplete_buff_recv),
				("since", max(connection.last_send_time, connection.last_recv_time)),
				("since", connection.start_time),
				("%.3f", connection.last_sent_time-connection.last_send_time),
				("%.0fkB", connection.bytes_sent/1024),
				("%.0fkB", connection.bytes_recv/1024),
				("%s", connection.last_cmd),
				("%s", connection.waiting_requests.keys()),
				("%s", connection.handshake.get("version")),
				("%s", connection.handshake.get("peer_id")),
			])
		yield "</table>"

		from greenlet import greenlet
		objs = [obj for obj in gc.get_objects() if isinstance(obj, greenlet)]
		yield "<br>Greenlets (%s):<br>" % len(objs)
		for obj in objs:
			yield " - %.3fkb: %s<br>" % (self.getObjSize(obj, hpy), cgi.escape(repr(obj)))


		from Worker import Worker
		objs = [obj for obj in gc.get_objects() if isinstance(obj, Worker)]
		yield "<br>Workers (%s):<br>" % len(objs)
		for obj in objs:
			yield " - %.3fkb: %s<br>" % (self.getObjSize(obj, hpy), cgi.escape(repr(obj)))


		from Connection import Connection
		objs = [obj for obj in gc.get_objects() if isinstance(obj, Connection)]
		yield "<br>Connections (%s):<br>" % len(objs)
		for obj in objs:
			yield " - %.3fkb: %s<br>" % (self.getObjSize(obj, hpy), cgi.escape(repr(obj)))


		from Site import Site
		objs = [obj for obj in gc.get_objects() if isinstance(obj, Site)]
		yield "<br>Sites (%s):<br>" % len(objs)
		for obj in objs:
			yield " - %.3fkb: %s<br>" % (self.getObjSize(obj, hpy), cgi.escape(repr(obj)))


		objs = [obj for obj in gc.get_objects() if isinstance(obj, self.server.log.__class__)]
		yield "<br>Loggers (%s):<br>" % len(objs)
		for obj in objs:
			yield " - %.3fkb: %s<br>" % (self.getObjSize(obj, hpy), cgi.escape(repr(obj.name)))


		objs = [obj for obj in gc.get_objects() if isinstance(obj, UiRequest)]
		yield "<br>UiRequest (%s):<br>" % len(objs)
		for obj in objs:
			yield " - %.3fkb: %s<br>" % (self.getObjSize(obj, hpy), cgi.escape(repr(obj)))

		objs = [(key, val) for key, val in sys.modules.iteritems() if val is not None]
		objs.sort()
		yield "<br>Modules (%s):<br>" % len(objs)
		for module_name, module in objs:
			yield " - %.3fkb: %s %s<br>" % (self.getObjSize(module, hpy), module_name, cgi.escape(repr(module)))

		yield "Done in %.3f" % (time.time()-s)
