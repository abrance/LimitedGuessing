import json
import sys
# import pytest_ordering
import time

import requests
from pathlib import Path

p = Path.cwd()
sys.path.insert(0, str(p.resolve()))


from test._config import Config


def get_url(api):
    _url = 'http://{}:{}'.format(Config.host, Config.port)
    return '{}{}'.format(_url, api)


def check_ret(ret):
    assert ret.ok
    res = ret.json()
    assert ["code", "data", "msg"] == list(res.keys())
    assert res["code"] == 200


def test_global_game_init():
    url = get_url('/api/init')
    data = {'user': "xiaoY", "password": "110"}
    ret = requests.post(url, data=json.dumps(data))
    check_ret(ret)
    time.sleep(1)


def test_get_tables_info():
    # 依赖
    test_global_game_init()

    time.sleep(1)
    url = get_url('/api/table_list')
    ret = requests.get(url)
    check_ret(ret)


def test_get_table_info():
    # 依赖
    test_global_game_init()

    url = get_url('/api/table_info')
    data = {"table_id": 0}
    ret = requests.get(url, data=json.dumps(data))
    check_ret(ret)
    res = ret.json()
    return res


def test_list_game_players():
    # lay
    test_global_game_init()

    url = get_url('/api/players_list')
    ret = requests.get(url)
    check_ret(ret)
    res = ret.json()
    return res


def test_set_player():
    # lay
    test_global_game_init()

    url = get_url('/api/set/player')
    for name in ["abran", "Dum"]:
        data = {
            'nickname': name
        }
        ret = requests.post(url, data=json.dumps(data))
        check_ret(ret)

    time.sleep(1)
    # 验证结果
    res = test_list_game_players()
    ls = [i.get('name') for i in res.get('data')]
    for i in ["abran", "Dum"]:
        assert i in ls

    return res


def test_add_player_to_table():
    # lay
    res = test_set_player()
    data = res.get('data')
    pid_ls = [i.get('pid') for i in data]
    if len(pid_ls) > 2:
        _pid_ls = pid_ls[-2:]
    else:
        _pid_ls = pid_ls

    url = get_url("/api/add/player")
    for pid in _pid_ls:
        data = {
            'table_id': 0,
            'player_id': pid
        }
        ret = requests.post(url, data=json.dumps(data))
        check_ret(ret)

    # 验证
    res = test_get_table_info()
    data = res.get('data')
    players_id = list(data.get('players').keys())
    players_id = list(map(lambda x: int(x), players_id))
    # 在这里 player_id (当字典的键为int类型时发生)由int 变为 str，可能是经过了json变化后的反应
    assert set(_pid_ls).issubset(set(players_id))


def test_init_game():
    # lay
    test_add_player_to_table()

    url = get_url('/api/init_game')
    data = {
        'table_id': 0
    }
    ret = requests.post(url, data=json.dumps(data))
    check_ret(ret)

    # 验证
    res = test_get_table_info()
    assert res.get('data').get('status') is True


def test_get_table_player_stack(skip=False):
    # lay
    if skip:
        pass
    else:
        test_init_game()

    url = get_url('/api/table_player_stack')
    data = {
        'player_id': 0
    }
    ret = requests.get(url, data=json.dumps(data))
    check_ret(ret)
    res = ret.json()
    return res


def test_limit_guess_bid():
    # lay

    test_init_game()
    url = get_url('/api/bid/limit_guess')
    data = {
        'table_id': 0
    }
    ret = requests.post(url, data=json.dumps(data))
    check_ret(ret)
    time.sleep(1)

    res = test_get_table_player_stack(True)
    data = res.get('data')
    assert data


def test_limit_guess_put():
    # lay
    test_limit_guess_bid()

    url = get_url('/api/put/limit_guess')
    data = {
        'player_id': 0,
        'cards_point': ['R']
    }
    ret = requests.post(url, data=json.dumps(data))
    check_ret(ret)
    time.sleep(1)

    url = get_url('/api/table_player')
    data = {
        'player_id': 0,
        'table_id': 0
    }
    ret = requests.get(url, data=json.dumps(data))
    check_ret(ret)
