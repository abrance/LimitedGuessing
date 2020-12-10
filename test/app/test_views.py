import json
import sys

import requests
from pathlib import Path

p = Path.cwd()
sys.path.insert(0, str(p.resolve()))

from test._config import Config


def get_url(api):
    _url = 'http://{}:{}'.format(Config.host, Config.port)
    return '{}/api/init'.format(_url, api)


def test_global_game_init():
    url = get_url('{}/api/init')
    data = {'user': "xiaoY", "password": "110"}
    ret = requests.post(url, data=json.dumps(data))
    assert ret.ok
    res = ret.json()
    assert ["code", "data", "msg"] == list(res.keys())
    assert res["code"] == 200


def test_get_tables_info():
    url = get_url('/api/table_list')
    ret = requests.get(url)
    assert ret.ok
    res = ret.json()
    assert ["code", "data", "msg"] == list(res.keys())
    assert res["code"] == 200

