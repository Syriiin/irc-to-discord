from collections import namedtuple
import re

import discord

from irctodiscord.irc import IRCClient
from irctodiscord import formatter

ChannelPair = namedtuple("ChannelPair", ["irc_channel", "discord_channel_id"])

class Bridge(discord.Client):
    def __init__(self, config, *args, **kwargs):
        allowed_mentions = discord.AllowedMentions(everyone=False, users=True, roles=False, replied_user=True)
        intents = discord.Intents.default()
        intents.members = True
        super().__init__(*args, **kwargs, allowed_mentions=allowed_mentions, intents=intents)
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
        def format_name(name, escape_mention=True):
            colour = str(sum(ord(x) for x in name) % 12 + 2)    # seeded random num between 2-13
            if len(colour) == 1:
                colour = "0" + colour   # zero pad to be 2 digits
            formatted_name = name
            if escape_mention:
                formatted_name = f"{name[:1]}\u200b{name[1:]}"
            return f"\x03{colour}{formatted_name}\x03"

        # Get name of user being replied to (if any)
        reply_name = None
        is_discord_reply = False
        if message.reference and message.type == discord.MessageType.default:
            replied_message = None
            if message.reference.cached_message:
                replied_message = message.reference.cached_message
            elif isinstance(message.reference.resolved, discord.Message):
                replied_message = message.reference.resolved

            if replied_message is not None:
                if replied_message.author == self.user:
                    # parse bridge formatted name eg. "**<SpiderNight>**: ..."
                    match = re.match(r"\*\*<([\S]+)>\*\*", replied_message.content)
                    if match:
                        reply_name = match.group(1)
                else:
                    is_discord_reply = True
                    try:
                        reply_name = replied_message.author.nick or replied_message.author.name
                    except AttributeError:
                        # occurs when the message wasn't in the cache and so author is a User rather than a Member
                        reply_name = replied_message.author.name
                        
        if content:
            # Format message
            formatted_message = await formatter.discordToIrc(content, author, str(message.author.avatar_url), message.created_at, self.config["parseFormatting"], self.config["urlShortener"])

            # Check for passthrough
            if message.author.id in self.config["passthroughList"]:
                header = ""
            elif message.type != discord.MessageType.default:
                header = f"\x0314SYSTEM\x03: "
            elif reply_name is not None:
                header = f"<{format_name(author)} \u2192 {format_name(reply_name, is_discord_reply)}> "
            else:
                header = f"<{format_name(author)}> "

            complete_message = f"{header}{formatted_message}"

            # Relay message
            await self.irc_client.send_message(channel_pair.irc_channel, complete_message)
        
        for attachment in message.attachments:
            await self.irc_client.send_message(channel_pair.irc_channel, f"<{format_name(author)}> \x02{attachment.filename}:\x0F {attachment.url}")
        for embed in message.embeds:
            if embed.url != discord.Embed.Empty and embed.url not in content:
                if embed.title is not discord.Embed.Empty:
                    await self.irc_client.send_message(channel_pair.irc_channel, f"<{format_name(author)}> \x02{embed.title}:\x0F {embed.url}")
                else:
                    await self.irc_client.send_message(channel_pair.irc_channel, f"<{format_name(author)}> {embed.url}")
