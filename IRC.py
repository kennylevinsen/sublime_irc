import sublime, sublime_plugin
import sys,socket,threading,functools

def main_thread(callback, *args, **kwargs):
	sublime.set_timeout(functools.partial(callback, *args, **kwargs), 0)

def _make_text_safeish(text, fallback_encoding):
	try:
		unitext = text.decode('utf-8')
	except UnicodeDecodeError:
		unitext = text.decode(fallback_encoding)
	return unitext

class IrcThread(threading.Thread):
	def __init__(self,prettyprint,onconnect,server,nick,motd = False):
		threading.Thread.__init__(self)
		self.prettyprint = prettyprint
		self.onconnect = onconnect
		self.conserver = server
		self.connick = nick
		self.conchannel = ""
		self.motd = motd
		self.s = socket.socket()
		self.die = False
		self.connected = False

	def backprint(self,msg):
		main_thread(self.prettyprint, _make_text_safeish(msg, "iso-8859-1"))

	def join(self,channel):
		self.conchannel = channel
		return self.s.send("JOIN %s\r\n" % channel)

	def kick(self,user):
		return self.s.send("KICK %s\r\n" % user)

	def quit(self,reason): # DOESN'T WORK ATM
		self.die = True
		return self.s.send("QUIT "+reason)

	def nick(self,nick):
		self.connick = nick
		return self.s.send("NICK %s\r\n" % nick)

	def oper(self, user, pw):
		return self.s.send("OPER %s %s\r\n" % (user, pw))

	def ident(self,user,host,hostname,realname):
		return self.s.send("USER %s %s %s :%s\r\n" % (user, host, hostname, realname))

	def pong(self,ping):
		return self.s.send(ping.replace("PING","PONG")+"\r\n")

	def printmsg(self,chan,snd,msg):
		self.backprint("["+snd+"]: "+msg)

	def chanmsg(self,msg):
		if msg == None:
			return
		self.printmsg(self.conchannel,self.connick,msg)
		return self.s.send("PRIVMSG %s :%s\r\n" % (self.conchannel, msg))

	def privmsg(self,user,msg):
		if msg == None:
			return
		return self.s.send("PRIVMSG %s :%s\r\n" % (user, msg))

	def command(self, msg):
		if msg[0] == "/":
			args = msg.split(" ")
			if args[0].lower() == "/nick":
				self.nick(args[1])
			elif args[0].lower() == "/join":
				self.join(args[1])
			elif args[0].lower() == "/quit":
				self.quit(args[1])
			else:
				self.prettyprint("Unknown command")
		else:
			self.chanmsg(msg)

	def run(self):
		readbuffer = ""
		die = False

		self.s.connect((self.conserver,6667))
		self.nick(self.connick)
		self.ident(self.connick, self.conserver, "blah", self.connick)

		while True:
			# Simple readbuffer.
			d = self.s.recv(1024)
			if not d: break
			readbuffer += d
			temp = readbuffer.split("\n")
			readbuffer = temp.pop()

			for line in temp:
				line = line.rstrip()

				if line[0] == ':': # Prefix found!
					t = line.find(":", 1)

					# Check if the response contains a payload
					if t != -1:
						msg = line[t+1:len(line)]
						info = line[1:t].split(" ")
					else:
						info = line[1:len(line)].split(" ")
						msg = ""

					if info[0].find("!")!=-1: # We don't care about peoples hostnames
						info[0] = info[0].split("!")[0]

					if info[1] == "NOTICE": # Notification from server
						self.backprint(" -!- "+msg)
					elif info[1] == "PRIVMSG": # Private message
						if msg == "I command you to quit, "+self.connick:
							self.quit("As you request, master...")
							break
						self.printmsg(self.conchannel,info[0],msg)
					elif info[1] == "MODE": # Mode change
						if msg == "":
							self.backprint("Mode change (%s) for channel %s" % (info[3], info[2]))
						else:
							self.backprint("Mode change (%s) for user %s" % (msg, info[2]))
							if not self.connected:
								self.connected = True
								self.onconnect()
					elif info[1] == "JOIN": # Channel join
						self.backprint("%s joined %s" % (info[0], info[2]))
					elif info[1] == "NICK": # Change of nick
						self.backprint("%s changed nickname to %s", (info[0]), info[2])
					elif info[1] == "USER": # User connect
						#self.backprint("%s connected", info[0])
						pass
					elif info[1] == "SERVER": # Server communication
						#self.backprint("%s")
						pass
					elif info[1] == "TOPIC": # Topic...
						self.backprint("Topic of %s: %s", (info[2], msg))
					elif info[1] == "SQUIT": # Server quit
						pass
					elif info[1] == "PART": # Parting message
						self.backprint("%s parted from %s", (info[0], info[2]))
					elif info[1] == "QUIT":
						if info[0] == self.connick:
							self.backprint("You were disconnected from the server")
							self.backprint("Reason: %s" % msg)
							self.die = True
							break
						else:
							self.backprint("%s quit (%s)" % (info[0], msg))
					elif info[1] == "KICK":
						if msg != "":
							self.backprint("You were kicked out from %s by %s (%s)" % (info[2], info[0], msg))
						else:
							self.backprint("You were kicked out from %s by %s" % (info[2], info[0]))
					elif info[1] == "001": # Greeting
						self.backprint(" --- "+msg)
					elif info[1] == "002": # Host notification
						self.backprint(" --- "+msg)
					elif info[1] == "003": # Creation time
						self.backprint(" --- "+msg)
					elif info[1] == "004": # ?
						pass
					elif info[1] == "005": # Supported stuff
						pass
					elif info[1] == "250": # Highest conncetion count
						pass
					elif info[1] == "251": # Online users
						pass
					elif info[1] == "252": # Notification of IRC ops
						pass
					elif info[1] == "253": # ???
						pass
					elif info[1] == "254": # ???
						pass
					elif info[1] == "255": # Clients and servers
						pass
					elif info[1] == "265": # Local users
						pass
					elif info[1] == "266": # Global users
						pass
					elif info[1] == "353": # Userlist
						self.backprint("Users: "+msg)
					elif info[1] == "366": # End of userlist
						pass
					elif info[1] == "372": # MOTD
						if self.motd:
							self.backprint(" --- "+msg)
					elif info[1] == "375": # Start MOTD
						if self.motd:
							self.backprint("      ---------------- START OF MOTD ----------------")
					elif info[1] == "376": # End of MOTD
						if self.motd:
							self.backprint("      ----------------- END OF MOTD -----------------")
					elif info[1] == "412": # No text to send
						pass
					elif info[1] == "433": # Nick already in use
						self.backprint("Trying with %s1..." % self.connick)
						self.nick(self.connick+"1")
					else: # Unknown command
						self.backprint("(%s) %s - %s: %s" % (info[1], info[0], info[2], msg))
						self.backprint("("+info[1]+") "+info[0]+" - "+info[2]+": "+msg)
				elif line.startswith("PING"):
					self.pong(line)
			if self.die: break
		self.backprint("Terminating!")
		self.s.close()

		def run(self):
			pass

class IrcCommand(sublime_plugin.WindowCommand):
	def prettyprint(self,msg):
		edit = self.wnd.begin_edit()
		wndsize = self.wnd.size()
		self.wnd.insert(edit,wndsize,msg+"\n")
		self.wnd.end_edit(edit)
		print msg

	def connected(self):
		main_thread(self.window.show_input_panel,"IRC", "", self.sendmsg, None, None)

	def sendmsg(self,msg):
		self.thread.command(msg)
		self.window.show_input_panel("IRC", "", self.sendmsg, None, None)

	def run(self):
		self.wnd = self.window.new_file()
		self.wnd.set_scratch(True)
		self.wnd.set_name("IRC Chat")
		self.thread = IrcThread(self.prettyprint,self.connected,"irc.freenode.net","sublime_irc_test")
		self.thread.start()
