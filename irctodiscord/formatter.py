import re
import itertools
import requests_async

async def discordToIrc(message):
    def replaceFormatting(form, replacement, string):
        start_form = re.escape(form)
        end_form = re.escape(form[::-1])    # reverse it

        pattern = r"{}((?:(?!{}).)*?){}".format(start_form, start_form, end_form)
        str_split = re.split(pattern, string)

        if len(str_split) == 1: # no formatting required
            return str_split[0]

        new_str = ""
        for idx, part in enumerate(str_split):
            if idx % 2 == 1:
                if re.search(r"https?:\/\/[^ \n]*$", new_str):  #make sure this formatting is not part of a url
                    new_str += "{}{}{}".format(form, part, form[::-1])
                else:
                    new_str += "{}{}\x0F".format(replacement, part)
            else:
                new_str += part

        return new_str

    async def createHaste(text):
        try:
            response = await requests_async.post("https://hastebin.com/documents", data=text, timeout=15)
        except requests_async.exceptions.RequestException as e:
            return "<Error creating hastebin>"
        key = response.json()["key"]
        url = "https://hastebin.com/" + key
        return url

    formatting_table = [    #comment lines of this table to disable certain types of formatting relay
        ("***__",   "\x02\x1D\x1F"),    # ***__UNDERLINE BOLD ITALICS__***
        ("__***",   "\x02\x1D\x1F"),    # __***UNDERLINE BOLD ITALICS***__
        ("**__",    "\x02\x1F"),    # **__UNDERLINE BOLD__**
        ("__**",    "\x02\x1F"),    # __**UNDERLINE BOLD**__
        ("*__", "\x1D\x1F"),    # *__UNDERLINE ITALICS__*
        ("__*", "\x1D\x1F"),    # __*UNDERLINE ITALICS*__
        ("***", "\x02\x1D"),    # ***BOLD ITALICS***
        ("**_", "\x02\x1D"),    # **_BOLD ITALICS_**
        ("_**", "\x02\x1D"),    # _**BOLD ITALICS**_
        ("__",  "\x1F"),    # __UNDERLINE__
        ("**",  "\x02"),    # **BOLD**
        ("*",   "\x1D"),    # *ITALICS*
        ("_",   "\x1D"),    # _ITALICS_
        ("`",   "\x11"),    # `MONOSPACE`
        ("~~",  "\x1e") # ~~STRIKETHROUGH~~
    ]

    #replace codeblocks
    for match in re.finditer(r"```(?:\w+\n|\n)?(.+?)```", message, flags=re.S):
        message = message.replace(match.group(0), await createHaste(match.group(1)))

    #replace newlines
    if "\n" in message:
        message = message.replace("\n", " ")

    #replace formatting
    for form in formatting_table:
        message = replaceFormatting(form[0], form[1], message)

    #clean up emotes
    message = re.sub(r"<(:\w+:)\d+>", lambda m: m.group(1), message)

    # check message length and truncate + hastebin if needed
    if len(message) > 400:  # max length is 512, so lets leave 112 bytes for the preamble
        # can improve this later by estimating the message length from server -> client (eg. https://github.com/RenolY2/Renol-IRC/blob/8a906402e08e9ae6cce02b61ba728d14b31b578b/commandHandler.py#L123-L141)
        message = message[:350] + "\x0F... {}".format(await createHaste(message))

    return message

async def ircToDiscord(message, discord_channel_id, discord_client):
    message = re.sub(r"\x03\d{0,2}(?:,\d{0,2})?", "", message)

    formatting_table = [
        (["\x02", "\x1D", "\x1F"],  "***__"),   #bold italics underline
        (["\x1D", "\x1F"],  "*__"), #italics underline
        (["\x02", "\x1F"],  "**_"), #bold underline
        (["\x02", "\x1D"],  "***"), #bold italics
        (["\x02"],  "**"),  #bold
        (["\x1D"],  "*"),   #italics
        (["\x1F"],  "__"),  #underline
        (["\x11"],  "`"),   #code
        (["\x1e"],  "~~")   #strikethrough
    ]

    for form in formatting_table:
        #check for matches for all permutation of the list
        perms = itertools.permutations(form[0])
        for perm in perms:
            if "\x0F" not in message:
                message += "\x0F"
            message = re.sub(r"{}(.*?)\x0F".format("".join(perm)), lambda m: "{}{}{}".format(form[1], m.group(1), form[1][::-1]), message)

    for char in ["\x02", "\x1D", "\x1F", "\x0F"]:
        message = message.replace(char, "")

    mentions = re.findall(r"@(\S+)", message)
    if mentions:
        def mentionGetter(name_match):
            name = name_match.group(1)
            for member in discord_client.get_channel(discord_channel_id).server.members:    #dota2mods serverid
                if member.name.lower() == name.lower() or (member.nick and member.nick.lower() == name.lower()):
                    return member.mention
            # user was not found, just return original text
            return "@" + name
        message = re.sub(r"@(\S+)", mentionGetter, message)

    return message
