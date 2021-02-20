import re
import itertools
import httpx
import json
import asyncio
import base64
import traceback

class MalformedConfig(Exception):
    pass

async def discordToIrc(message, author, author_avatar_url, parse_formatting=True, url_shortener_config=None):
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

    async def createTermbin(text):
        reader, writer = await asyncio.wait_for(asyncio.open_connection("termbin.com", 9999), timeout=5)
        writer.write(text.encode())
        response = await reader.readline()
        writer.close()
        url = response.decode().strip()
        return url

    async def createHaste(text):
        async with httpx.AsyncClient() as client:
            response = await client.post("https://hastebin.com/documents", data=text, timeout=5)
        key = response.json()["key"]
        url = "https://hastebin.com/" + key
        return url

    async def createTextDump(text):
        try:
            return await createHaste(text)
        except (httpx.HTTPError, json.JSONDecodeError, KeyError):
            try:
                return await createTermbin(text)
            except asyncio.TimeoutError:
                return "<Error creating text dump>"

    async def createDiscohookUrl(message, author, author_avatar_url, url_shortener_config):
        discohook_data = {
            "messages": [
                {
                    "data": {
                        "content": message,
                        "username": author,
                        "avatar_url": author_avatar_url
                    },
                    "badge": None
                }
            ]
        }
        base64_string = base64.urlsafe_b64encode(json.dumps(discohook_data).encode()).decode()
        discohook_url = f"https://discohook.org/viewer?data={base64_string}"
        
        if "service" not in url_shortener_config:
            raise MalformedConfig("Missing 'service' property in url shortener config")

        if url_shortener_config["service"] == "r.xpaw.me":
            if "token" not in url_shortener_config:
                raise MalformedConfig(f"Missing config property 'token' of url shortener service 'r.xpaw.me'")
            async with httpx.AsyncClient() as client:
                form_data = {
                    "secret": url_shortener_config["token"],
                    "url": discohook_url
                }
                response = await client.post("https://r.xpaw.me/@create", data=form_data, timeout=5)
                if response.status_code != 201:
                    raise MalformedConfig(f"Something went wrong in request to url shortener service 'r.paw.me': HTTP {response.status_code}")
                return response.read().decode()
        else:
            raise MalformedConfig(f"The url shortener service '{url_shortener_config['service']}' is not supported")

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

    # if we have codeblocks and a shortener available, just try to throw the message into discohook
    if url_shortener_config is not None and re.search(r"```(.+?)```", message, flags=re.S) is not None:
        try:
            return await createDiscohookUrl(message, author, author_avatar_url, url_shortener_config)
        except (httpx.HTTPError, MalformedConfig) as error:
            traceback.print_exc()

    #replace codeblocks
    for match in re.finditer(r"```(?:\w+\n|\n)?(.+?)```", message, flags=re.S):
        code = match.group(1).strip("\n")
        if code.count("\n") > 0:
            dump_link = await createTextDump(code)
            message = message.replace(match.group(0), dump_link)
        else:
            message = message.replace(match.group(0), f"\x11{code}\x11")

    #replace newlines
    if "\n" in message:
        message = message.replace("\n", " ")

    #replace formatting
    if parse_formatting:
        for form in formatting_table:
            message = replaceFormatting(form[0], form[1], message)

    #clean up emotes
    message = re.sub(r"<(:\w+:)\d+>", lambda m: m.group(1), message)

    # check message length and truncate + hastebin if needed
    if len(message) > 400:  # max length is 512, so lets leave 112 bytes for the preamble
        # can improve this later by estimating the message length from server -> client (eg. https://github.com/RenolY2/Renol-IRC/blob/8a906402e08e9ae6cce02b61ba728d14b31b578b/commandHandler.py#L123-L141)
        if url_shortener_config is not None:
            try:
                return await createDiscohookUrl(message, author, author_avatar_url, url_shortener_config)
            except (httpx.HTTPError, MalformedConfig) as error:
                traceback.print_exc()
        message = message[:350] + "\x0F... {}".format(await createTextDump(message))

    return message

async def ircToDiscord(message, discord_channel_id, discord_client, parse_formatting=True):
    message = re.sub(r"\x03\d{0,2}(?:,\d{0,2})?", "", message)

    if parse_formatting:
        formatting_table = [
            (["\x02", "\x1D", "\x1F"],  "***__"),   #bold italics underline
            (["\x1D", "\x1F"],  "*__"), #italics underline
            (["\x02", "\x1F"],  "**_"), #bold underline
            (["\x02", "\x1D"],  "***"), #bold italics
            (["\x02"],  "**"),  #bold
            (["\x1D"],  "*"),   #italics
            (["\x1F"],  "__"),  #underline
            (["\x11"],  "`"),   #code
            (["\x1E"],  "~~")   #strikethrough
        ]

        for form in formatting_table:
            #check for matches for all permutation of the list
            perms = itertools.permutations(form[0])
            for perm in perms:
                if "\x0F" not in message:
                    message += "\x0F"
                message = re.sub(r"{}(.*?)\x0F".format("".join(perm)), lambda m: "{}{}{}".format(form[1], m.group(1), form[1][::-1]), message)

    for char in ["\x02", "\x1D", "\x1F", "\x11", "\x1E", "\x0F"]:
        message = message.replace(char, "")

    mentions = re.findall(r"@(\S+)", message)
    if mentions:
        def mentionGetter(name_match):
            name = name_match.group(1)
            lower_name = name.lower()
            for member in discord_client.get_channel(discord_channel_id).guild.members:
                if member.name.lower() == lower_name or (member.nick and member.nick.lower() == lower_name):
                    return member.mention
            # user was not found, just return original text
            return "@" + name
        message = re.sub(r"@(\S+)", mentionGetter, message)

    return message
