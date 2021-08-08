import hashlib
import json
import pathlib
import random
import re
import string


def escape_ansi(line):
    ansi_escape = re.compile(r'(\x9B|\x1B\[)[0-?]*[ -/]*[@-~]')
    return ansi_escape.sub('', line).strip()


def rand_token(n):
    return ''.join(
        random.choice(string.ascii_letters + string.digits) for _ in range(n)
    )


def hash(obj):
    """
    Since hash() is not guaranteed to give the same result in different
    sessions, we will be using hashlib for more consistent hash_ids
    """
    if isinstance(obj, (set, tuple, list, dict)):
        obj = repr(obj)
    hash_id = hashlib.md5()
    hash_id.update(repr(obj).encode('utf-8'))
    hex_digest = str(hash_id.hexdigest())
    return hex_digest


def set_pairlist(coin: str, config: pathlib.Path):
    config_json = json.loads(config.read_text())
    config_json['exchange']['pair_whitelist'] = [coin]
    with config.open('w') as f:
        json.dump(config_json, f)
