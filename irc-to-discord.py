import discord
import asyncio
import logging
import sys
import time
import threading
import json

import uniirc
import uniformatter

print(sys.version)
print(discord.__version__)

logger = logging.getLogger('discord')
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

with open("config.json") as fp:
	config = json.load(fp)
chan_pairs = [ (pair["irc_channel"], pair["discord_channel"]) for pair in config["pairs"] ]

client = discord.Client()

irc_client = uniirc.IRCClient(chan_pairs=chan_pairs, config=config["irc"], discord_client=client)
irc_thread = None


@client.event
@asyncio.coroutine								#notifying console that bot is logged in
def on_ready():
	print("Logged into discord as user: {}".format(client.user.name))

	# discord login successful so we can connect to IRC
	print("Starting IRC...")
	global irc_thread
	irc_thread = threading.Thread(target=irc_client.irc_run, daemon=True)
	irc_thread.start()

	default_status = "with your messages"
	print("Setting default status: {}".format(default_status))
	yield from client.change_presence(activity=discord.Game(name=default_status))
	return


@client.event
@asyncio.coroutine								#on message recieved, execute this block
def on_message(msg):
	for chan in chan_pairs:
		if msg.channel.id == chan[1] and msg.author.id != 263688414296145920:		#is bridge channel and not uni herself
			yield from msg_process(msg, chan[0])
	return


@asyncio.coroutine
def msg_process(msg, chan):
	#Nickname check
	if msg.author.nick:
		author = msg.author.nick
	else:
		author = msg.author.name

	#Formatting
	clean_msg = uniformatter.discordToIrc(msg.clean_content)

	#Sending
	author = author[:1] + u'\u200b' + author[1:]
	colour = str((sum([ ord(x) for x in author ]) % 12) + 2)		#get seeded random num between 2-13
	if len(colour) == 1:
		colour = "0" + colour

	if clean_msg:
		irc_client.send_message(chan, "<\x03{}{}\x03> {}".format(colour, author, clean_msg))
	for attachment in msg.attachments:
		irc_client.send_message(chan, "<\x03{}{}\x03> \x02{}:\x0F {}".format(colour, author, attachment["filename"], attachment["url"]))
	for embed in msg.embeds:
		irc_client.send_message(chan, "<\x03{}{}\x03> \x02{}:\x0F {}".format(colour, author, embed["title"], embed["url"]))
	return



@asyncio.coroutine			#if irc thread has died then main program exits too
def irc_checker():
	yield from client.wait_until_ready()
	while not client.is_closed:
		if irc_thread and not irc_thread.is_alive():
			exit("IRC client disconnected. Exiting...")
		yield from asyncio.sleep(10)
	return



print("Starting Discord...")

loop = asyncio.get_event_loop()

try:
	loop.create_task(irc_checker())
	loop.run_until_complete(client.login(config["discord"]["login_token"]))
	loop.run_until_complete(client.connect())
except Exception:
	loop.run_until_complete(client.close())
finally:
	loop.close()
