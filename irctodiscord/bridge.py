from collections import namedtuple

import discord

from irctodiscord.irc import IRCClient
from irctodiscord import formatter

ChannelPair = namedtuple("ChannelPair", ["irc_channel", "discord_channel_id"])

class Bridge(discord.Client):
    def __init__(self, config, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config = config["discord"]
        self.channel_pairs = [ChannelPair(pair["irc_channel"], pair["discord_channel"]) for pair in config["pairs"]]
        self.irc_client = IRCClient(self, config["irc"], self.channel_pairs)

    def run(self):
        self.irc_client_task = self.loop.create_task(self.irc_client.start())
        super().run(self.config["login_token"])

    async def on_ready(self):
        await self.change_presence(activity=discord.Game(name=self.config["status_msg"]))
    
    async def on_message(self, message):
        if message.author.id not in self.config["ignoreList"] + [self.user.id]:
            pair = next((pair for pair in self.channel_pairs if pair.discord_channel_id == message.channel.id), None)
            if pair:
                await self.process_message(message, pair)

    async def process_message(self, message, channel_pair):
        # Get author name
        author = message.author.nick or message.author.name

        if message.content:
            # Format message
            formatted_message = await formatter.discordToIrc(message.clean_content)

            # Check for passthrough
            if message.author.id not in self.config["passthroughList"]:
                # Format author
                author = author[:1] + u"\u200b" + author[1:]
                colour = str(sum(ord(x) for x in author) % 12 + 2)    # seeded random num between 2-13
                if len(colour) == 1:
                    # zero pad to be 2 digits
                    colour = "0" + colour
                complete_message = "<\x03{}{}\x03> {}".format(colour, author, formatted_message)
            else:
                complete_message = formatted_message

            # Relay message
            await self.irc_client.send_message(channel_pair.irc_channel, complete_message)
        
        for attachment in message.attachments:
            await self.irc_client.send_message(chan, "<\x03{}{}\x03> \x02{}:\x0F {}".format(colour, author, attachment.filename, attachment.url))
        for embed in message.embeds:
            await self.irc_client.send_message(chan, "<\x03{}{}\x03> \x02{}:\x0F {}".format(colour, author, embed.title, embed.url))
