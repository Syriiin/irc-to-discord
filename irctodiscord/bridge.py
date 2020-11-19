from collections import namedtuple

import discord

from irctodiscord.irc import IRCClient
from irctodiscord import formatter

ChannelPair = namedtuple("ChannelPair", ["irc_channel", "discord_channel_id"])

class Bridge(discord.Client):
    def __init__(self, config, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config = config["discord"]
        self.channel_pairs = [ChannelPair(pair["ircChannel"], pair["discordChannel"]) for pair in config["pairs"]]
        self.irc_client = IRCClient(self, config["irc"], self.channel_pairs)

    def run(self):
        self.irc_client_task = self.loop.create_task(self.irc_client.start())
        print("Starting discord client...")
        super().run(self.config["loginToken"])

    async def on_ready(self):
        print("Connected to discord.")
        await self.change_presence(activity=discord.Game(name=self.config["statusMessage"]))
    
    async def on_message(self, message):
        if message.author.id not in self.config["ignoreList"] + [self.user.id]:
            pair = next((pair for pair in self.channel_pairs if pair.discord_channel_id == message.channel.id), None)
            if pair:
                await self.process_message(message, pair)

    async def process_message(self, message, channel_pair):
        # Get author name
        try:
            author = message.author.nick or message.author.name
        except AttributeError:
            # possible for system messages or PMs (not relevant to this bot)
            author = message.author.name

        if message.type == discord.MessageType.default:
            content = message.clean_content
        else:
            content = message.system_content

        # Format author
        author = author[:1] + u"\u200b" + author[1:]
        colour = str(sum(ord(x) for x in author) % 12 + 2)    # seeded random num between 2-13
        if len(colour) == 1:
            # zero pad to be 2 digits
            colour = "0" + colour

        if content:
            # Format message
            formatted_message = await formatter.discordToIrc(content) if self.config["parseFormatting"] else content

            # Check for passthrough
            if message.author.id in self.config["passthroughList"]:
                complete_message = formatted_message
            elif message.type != discord.MessageType.default:
                complete_message = f"\x0314SYSTEM\x03: {formatted_message}"
            else:
                complete_message = f"<\x03{colour}{author}\x03> {formatted_message}"

            # Relay message
            await self.irc_client.send_message(channel_pair.irc_channel, complete_message)
        
        for attachment in message.attachments:
            await self.irc_client.send_message(channel_pair.irc_channel, f"<\x03{colour}{author}\x03> \x02{attachment.filename}:\x0F {attachment.url}")
        for embed in message.embeds:
            await self.irc_client.send_message(channel_pair.irc_channel, f"<\x03{colour}{author}\x03> \x02{embed.title}:\x0F {embed.url}")
