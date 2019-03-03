import re
import itertools
import requests

def discordToIrc(msg):
	def replaceFormatting(form, replacement, string):
		start_form = re.escape(form)
		end_form = re.escape(form[::-1])	# reverse it

		pattern = r"{}((?:(?!{}).)*?){}".format(start_form, start_form, end_form)
		str_split = re.split(pattern, string)

		if len(str_split) == 1:	# no formatting required
			return str_split[0]

		new_str = ""
		for idx, part in enumerate(str_split):
			if idx % 2 == 1:
				if re.search(r"https?:\/\/[^ \n]*$", new_str):	#make sure this formatting is not part of a url
					new_str += "{}{}{}".format(form, part, form[::-1])
				else:
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
		("***__",	"\x02\x1D\x1F"),	# ***__UNDERLINE BOLD ITALICS__***
		("__***",	"\x02\x1D\x1F"),	# __***UNDERLINE BOLD ITALICS***__
		("**__",	"\x02\x1F"),		# **__UNDERLINE BOLD__**
		("__**",	"\x02\x1F"),		# __**UNDERLINE BOLD**__
		("*__",		"\x1D\x1F"),		# *__UNDERLINE ITALICS__*
		("__*",		"\x1D\x1F"),		# __*UNDERLINE ITALICS*__
		("***",		"\x02\x1D"),		# ***BOLD ITALICS***
		("**_",		"\x02\x1D"),		# **_BOLD ITALICS_**
		("_**",		"\x02\x1D"),		# _**BOLD ITALICS**_
		("__",		"\x1F"),			# __UNDERLINE__
		("**",		"\x02"),			# **BOLD**
		("*",		"\x1D"),			# *ITALICS*
		("_",		"\x1D"),			# _ITALICS_
		("`",		"\x11"),			# `MONOSPACE`
		("~~",		"\x1e")				# ~~STRIKETHROUGH~~
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
	msg = re.sub(r"\x03\d{0,2}(?:,\d{0,2})?", "", msg)

	formatting_table = [
		(["\x02", "\x1D", "\x1F"],	"***__"),	#bold italics underline
		(["\x1D", "\x1F"],			"*__"),		#italics underline
		(["\x02", "\x1F"],			"**_"),		#bold underline
		(["\x02", "\x1D"],			"***"),		#bold italics
		(["\x02"],					"**"),		#bold
		(["\x1D"],					"*"),		#italics
		(["\x1F"],					"__")		#underline
		(["\x11"],					"`")		#code
		(["\x1e"],					"~~")		#strikethrough
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
		def mentionGetter(name_match):
			name = name_match.group(1)
			for member in discord_client.get_channel(channel).server.members:	#dota2mods serverid
				if member.name.lower() == name.lower() or (member.nick and member.nick.lower() == name.lower()):
					return member.mention
			# user was not found, just return original text
			return "@" + name
		msg = re.sub(r"@(\S+)", mentionGetter, msg)

	return msg
