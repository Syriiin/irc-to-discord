import discord
import asyncio
import logging
import sys
import time
import threading

import uniirc
import uniformatter

print(sys.version)
print(discord.__version__)

logger = logging.getLogger('discord')
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

fp_logininfo = open("logininfo.txt", "r")
logintoken = fp_logininfo.read()				#reading login token from logininfo.txt as of OAuth2 update with BOT accounts
fp_logininfo.close()

chan_pairs = [	#(irc channel name, discord channel id)
	("#dota2mods", "250160069549883392"),
	("#dota2modhelpdesk", "259577266290294786"),
	("#dota2ai", "259185445131386881"),
]

voice_list = [
	"111342297999802368",	# @Syrin
]

client = discord.Client()

irc_client = uniirc.IRCClient(chan_pairs=chan_pairs, discord_client=client)


@client.event
@asyncio.coroutine								#notifying console that bot is logged in
def on_ready():
	print("Logged into discord as user: 「{}」".format(client.user.name))
	default_status = "with your messages"
	print("Setting default status: {}".format(default_status))
	yield from client.change_presence(game=discord.Game(name=default_status))
	return


@client.event
@asyncio.coroutine								#on message recieved, execute this block
def on_message(msg):
	for chan in chan_pairs:
		if msg.channel.id == chan[1] and msg.author.id != "263688414296145920":		#is bridge channel and not uni herself
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
	author = "\x81".join(list(author))
	if len(author) > 1:
		author = author[:1] + "\x81" + author[1:]
	colour = str((sum([ ord(x) for x in author ]) % 12) + 2)		#get seeded random num between 2-13
	if len(colour) == 1:
		colour = "0" + colour

	irc_client.send_message(chan, "<\x03{}{}\x03> {}".format(colour, author, clean_msg))
	return



@asyncio.coroutine			#if irc thread has died then main program exits too
def irc_checker():
	yield from client.wait_until_ready()
	while not client.is_closed:
		if not irc_thread.is_alive():
			exit("IRC client disconnected. Exiting...")
		yield from asyncio.sleep(10)
	return



print("Starting Discord...")

loop = asyncio.get_event_loop()


print("Starting IRC...")

irc_thread = threading.Thread(target=irc_client.irc_run, daemon=True)
irc_thread.start()

try:
	loop.create_task(irc_checker())
	loop.run_until_complete(client.login(logintoken))
	loop.run_until_complete(client.connect())
except Exception:
	loop.run_until_complete(client.close())
finally:
	loop.close()
