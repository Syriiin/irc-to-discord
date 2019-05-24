# irc-to-discord
IRC to Discord and vise-versa chat relay

## Requirements

- Python 3 (untested below 3.7)
- Discord.py (untested below 1.1.1)
- Async-requests

## Setup

1. Install dependencies
    ```
    $ pip install -r requirements.txt
    ```
2. Make a copy of `config.template.json` named `config.json`
3. Modify contents of `config.json` to your desired settings and delete all comments
4. Ensure that your `config.json` is not being committed to the repo to keep your auth credentials private
5. Run `main.py` with python
    ```
    $ python main.py
    ```
