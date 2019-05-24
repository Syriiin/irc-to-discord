import json

from irctodiscord.bridge import Bridge

with open("config.json") as fp:
    config = json.load(fp)

bridge = Bridge(config)

bridge.run()
