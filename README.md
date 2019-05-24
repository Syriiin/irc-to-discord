# irc-to-discord
IRC to Discord and vise-versa chat relay

## Requirements

- Python 3 ( untested below 3.7 )
- Discord.py ( `pip install discord.py`, untested below 1.1.1 )
- Requests ( `pip install requests` )

## Setup

1. Make a copy of `config.template.json` named `config.json`
2. Modify contents of `config.json` to your desired settings and delete all comments
3. Ensure that your `config.json` is not being committed to the repo to keep your auth credentials private
4. Run `irc-to-discord.py` with python
