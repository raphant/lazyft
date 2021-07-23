import json
import pathlib
import random
import re
import string


def escape_ansi(line):
    ansi_escape = re.compile(r'(\x9B|\x1B\[)[0-?]*[ -\/]*[@-~]')
    return ansi_escape.sub('', line).strip()


def rand_token():
    return ''.join(
        random.choice(string.ascii_letters + string.digits) for _ in range(6)
    )


def set_pairlist(coin: str, config: pathlib.Path):
    config_json = json.loads(config.read_text())
    config_json['exchange']['pair_whitelist'] = [coin]
    with config.open('w') as f:
        json.dump(config_json, f)
