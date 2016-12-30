import socket
from datetime import datetime
import asyncio
import discord

import uniformatter

class IRCClient:
	def __init__(self, chan_pairs, discord_client):
		self.chan_pairs = chan_pairs
		self.discord_client = discord_client
		self.s, self.server, self.channels, self.nick = self.irc_connect()

	def irc_connect(self):
		server = "irc.gamesurge.net"
		port = 6667

		print("Connecting to {}:{}".format(server, port))

		channels = [ pair[0] for pair in self.chan_pairs ]
		nick = "UniBridge"

		s = socket.socket()

		s.connect((server, port))
		s.send("NICK {}\r\n".format(nick).encode())
		s.send("USER {} * * {}\r\n".format(nick, nick).encode())

		print("Connected.")

		return s, server, channels, nick

	def join_channels(self):
		for channel in self.channels:
			print("Joining {}".format(channel))
			self.s.send("JOIN {}\r\n".format(channel).encode())
		return

	def msg_process(self, rawmsg):		#figure out what we want to do with our irc message
		prefix, command, args, msg = self.split_msg(rawmsg)

		#msg format is "nick PRIVMSG #channel :message"
		if command in ["376", "422"]:
			print("END OF MOTD")
			self.join_channels()

		elif command == "PING":
			self.s.send("PONG {}\r\n".format(msg).encode())
			print("PONG'd")

		elif command == "PRIVMSG":
			author = prefix.split("!")[0]

			#send message to run comm coroutine
			for pair in self.chan_pairs:
				if args[0] == pair[0]:
					clean_msg = uniformatter.ircToDiscord(msg, pair[1], self.discord_client)
					asyncio.run_coroutine_threadsafe(self.discord_client.send_message(discord.Object(id=pair[1]), "**<{}>** {}".format(author, clean_msg)), self.discord_client.loop)

			if msg == "hello uni":
				self.s.send("PRIVMSG {} :{}\r\n".format(args[0], "I'm a qt pi").encode())
			# elif msg == "uni dc":
			# 	self.s.send("QUIT :{}\r\n".format("Because I was told to").encode())
			# 	exit("I was told to")
		return

	def split_msg(self, rawmsg):			#interpret irc message
		msgpre, sep, msg = rawmsg.partition(" :")

		if not sep:			#if sep is empty
			msg = None

		msgpre_list = msgpre.split()

		if msgpre_list[0].startswith(":"):
			prefix = msgpre_list.pop(0).lstrip(":")
		else:
			prefix = None

		command = msgpre_list.pop(0)

		args = msgpre_list

		return prefix, command, args, msg

	def irc_run(self):		#start main irc loop
		line_buffer = ""

		while True:
			responce = self.s.recv(2048)

			line_buffer += responce.decode()
			lines = line_buffer.split("\n")

			line_buffer = lines.pop()

			for line in lines:
				line = line.rstrip()

				if line:
					self.msg_process(line)
				else:
					pass


	def send_message(self, channel, msg):		#send irc message
		self.s.send("PRIVMSG {} :{}\r\n".format(channel, msg).encode())
		return

