import asyncio
import re
import socket

from irctodiscord import formatter

class IRCClient:
    def __init__(self, discord_client, config, channel_pairs):
        self.discord_client = discord_client
        self.config = config
        self.channel_pairs = channel_pairs
        self.connected = False

    async def send_message(self, channel, message):
        try:
            self.writer.write("PRIVMSG {} :{}\r\n".format(channel, message).encode())
        except BrokenPipeError as e:
            exit("Error: message size too large. Exiting...")

    def split_message(self, raw_message):
        message_pre, sep, message = raw_message.partition(" :")

        if not sep:
            # if sep is empty
            message = None

        message_pre_list = message_pre.split()

        if message_pre_list[0].startswith(":"):
            prefix = message_pre_list.pop(0).lstrip(":")
        else:
            prefix = None

        command = message_pre_list.pop(0)

        args = message_pre_list

        return prefix, command, args, message

    async def process_message(self, raw_message):
        prefix, command, args, message = self.split_message(raw_message)

        # message format is "nick PRIVMSG #channel :message"
        if command in ["376", "422"]:
            # end of MOTD
            await self.join_channels()
        elif command == "PING":
            self.writer.write("PONG {}\r\n".format(message).encode())
        elif command == "PRIVMSG":
            author = prefix.split("!")[0]
            if author in self.config["ignoreList"]:
                return

            # send message to run comm coroutine
            pair = next((pair for pair in self.channel_pairs if pair.irc_channel == args[0]), None)
            if pair:
                if message.startswith("=status") and len(message.split()) > 1:
                    name = message.split(" ", 1)[1].lower()
                    status_message = ""
                    member = next(member for member in self.discord_client.get_channel(pair.discord_channel_id).server.members if member.name.lower() == name or (member.nick and member.nick.lower() == name))
                    status_message = "{} is currently {}".format(member.name, str(member.status))
                    await self.send_message(args[0], status_message)

                formatted_message = await formatter.ircToDiscord(message, pair.discord_channel_id, self.discord_client)
                action_regex = re.match(r"\u0001ACTION (.+)\u0001", formatted_message)  # format /me
                if action_regex:
                    complete_message = "**\* {}** {}".format(author, action_regex.group(1))
                else:
                    if author not in self.config["passthroughList"]:
                        complete_message = "**<{}>** {}".format(author, formatted_message)
                    else:
                        complete_message = formatted_message
                    
                discord_channel = self.discord_client.get_channel(pair.discord_channel_id)
                await discord_channel.send(complete_message)

    async def join_channels(self):
        for pair in self.channel_pairs:
            self.writer.write("JOIN {}\r\n".format(pair.irc_channel).encode())

    async def connect(self):
        self.reader, self.writer = await asyncio.open_connection(self.config["server"], self.config["port"], loop=self.discord_client.loop)
        self.writer.write("NICK {}\r\n".format(self.config["nickname"]).encode())
        self.writer.write("USER {} * * {}\r\n".format(self.config["nickname"], self.config["nickname"]).encode())
        self.connected = True

    async def start(self):
        if not self.connected:
            await self.connect()
        
        line_buffer = ""

        while True:
            response = await self.reader.read(2048)

            line_buffer += response.decode()
            lines = line_buffer.split("\n")

            line_buffer = lines.pop()

            for line in lines:
                line = line.rstrip()

                if line:
                    await self.process_message(line)
    
    async def close(self):
        self.writer.close()
