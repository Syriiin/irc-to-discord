import re
import itertools
import requests

def discordToIrc(msg):
	def replaceFormatting(form, replacement, string):
		pattern = r"{}((?:(?!{}).)*?){}".format(form[0], form[0], form[1])
		str_split = re.split(pattern, string)

		new_str = ""
		for idx, part in enumerate(str_split):
			if idx % 2 == 1:
				new_str += "{}{}\x0F".format(replacement, part)
			else:
				new_str += part

		return new_str

	def createHaste(code):
		responce = requests.post("https://hastebin.com/documents", data=code)
		key = responce.json()["key"]
		url = "https://hastebin.com/" + key
		return url

	formatting_table = [		#comment lines of this table to disable certain types of formatting relay
		( (r"\*{3}_{2}",	r"_{2}\*{3}"),	"\x02\x1D\x1F"),	# ***__UNDERLINE BOLD ITALICS__***
		( (r"_{2}\*{3}",	r"\*{3}_{2}"),	"\x02\x1D\x1F"),	# __***UNDERLINE BOLD ITALICS***__
		( (r"\*{2}_{2}",	r"_{2}\*{2}"),	"\x02\x1F"),		# **__UNDERLINE BOLD__**
		( (r"_{2}\*{2}",	r"\*{2}_{2}"),	"\x02\x1F"),		# __**UNDERLINE BOLD**__
		( (r"\*_{2}",		r"_{2}\*"),		"\x1D\x1F"),		# *__UNDERLINE ITALICS__*
		( (r"_{2}\*",		r"\*_{2}"),		"\x1D\x1F"),		# __*UNDERLINE ITALICS*__
		( (r"\*{3}",		r"\*{3}"),		"\x02\x1D"),		# ***BOLD ITALICS***
		( (r"\*{2}_",		r"_\*{2}"),		"\x02\x1D"),		# **_BOLD ITALICS_**
		( (r"_\*{2}",		r"\*{2}_"),		"\x02\x1D"),		# _**BOLD ITALICS**_
		( (r"_{2}",			r"_{2}"),		"\x1F"),			# __UNDERLINE__
		( (r"\*{2}",		r"\*{2}"),		"\x02"),			# **BOLD**
		( (r"\*",			r"\*"),			"\x1D"),			# *ITALICS*
		( (r"_",			r"_"),			"\x1D"),			# _ITALICS_
		( (r"`",			r"`"),			"\x0315")			# `code`
	]


	#replace codeblocks
	msg = re.sub(r"```(?:\w+\n|\n)?(.+?)```", lambda m: createHaste(m.group(1)), msg, flags=re.S)

	#replace newlines
	if "\n" in msg:
		msg = msg.replace("\n", " ")

	#replace formatting
	for form in formatting_table:
		msg = replaceFormatting(form[0], form[1], msg)

	#clean up emotes
	msg = re.sub(r"<(:\w+:)\d+>", lambda m: m.group(1), msg)

	return msg

def ircToDiscord(msg, channel, discord_client):
	msg = re.sub(r"\x03\d{0,2}", "", msg)

	formatting_table = [
		(["\x02", "\x1D", "\x1F"],	"***__"),	#bold italics underline
		(["\x1D", "\x1F"],			"*__"),		#italics underline
		(["\x02", "\x1F"],			"**_"),		#bold underline
		(["\x02", "\x1D"],			"***"),		#bold italics
		(["\x02"],					"**"),		#bold
		(["\x1D"],					"*"),		#italics
		(["\x1F"],					"__")		#underline
	]

	for form in formatting_table:
		#check for matches for all permutation of the list
		perms = itertools.permutations(form[0])
		for perm in perms:
			if "\x0F" not in msg:
				msg += "\x0F"
			msg = re.sub(r"{}(.*?)\x0F".format("".join(perm)), lambda m: "{}{}{}".format(form[1], m.group(1), form[1][::-1]), msg)

	for char in ["\x02", "\x1D", "\x1F", "\x0F"]:
		msg = msg.replace(char, "")

	mentions = re.findall(r"@(\S+)", msg)
	if mentions:
		def mentionGetter(name):
			name = name.group(1).lower()
			for member in discord_client.get_channel(channel).server.members:	#dota2mods serverid
				if member.name.lower() == name or (member.nick and member.nick.lower() == name):
					return member.mention
		msg = re.sub(r"@(\S+)", mentionGetter, msg)

	return msg
