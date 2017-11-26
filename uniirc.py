import socket
from datetime import datetime
import asyncio
import discord
import re

import _thread

import uniformatter

class IRCClient:
	def __init__(self, chan_pairs, config, discord_client):
		self.chan_pairs = chan_pairs
		self.discord_client = discord_client
		self.s, self.server, self.nick = self.irc_connect(**config)
		
	def irc_connect(self, server, port, nickname):
		print("Connecting to {}:{}".format(server, port))

		s = socket.socket()

		s.connect((server, port))
		s.send("NICK {}\r\n".format(nickname).encode())
		s.send("USER {} * * {}\r\n".format(nickname, nickname).encode())

		print("Connected.")

		return s, server, nickname

	def join_channels(self):
		for channel in [ pair[0] for pair in self.chan_pairs ]:
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
					if msg.startswith("=status") and len(msg.split()) > 1:
						name = msg.split(" ", 1)[1].lower()
						status_msg = ""
						for member in self.discord_client.get_channel(pair[1]).server.members:
							if member.name.lower() == name or (member.nick and member.nick.lower() == name):
								status_msg += "{} is currently {}".format(member.name, str(member.status))
						self.send_message(args[0], status_msg)
						continue

					clean_msg = uniformatter.ircToDiscord(msg, pair[1], self.discord_client)
					action_regex = re.match(r"\u0001ACTION (.+)\u0001", clean_msg)	#format /me
					if action_regex:
						formatted_msg = "**\* {}** {}".format(author, action_regex.group(1))
					else:
						formatted_msg = "**<{}>** {}".format(author, clean_msg)
					asyncio.run_coroutine_threadsafe(self.discord_client.send_message(discord.Object(id=pair[1]), formatted_msg), self.discord_client.loop)
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
		try:
			self.s.send("PRIVMSG {} :{}\r\n".format(channel, msg).encode())
		except BrokenPipeError as e:
			_thread.interrupt_main()
			# exit("Error in message size too large. Exiting...")
		return

