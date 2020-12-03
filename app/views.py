import json
import os
import sys

from flask import request

from app.config import set_player_queue, add_player_queue, gg_add_player_queue
from app.handler import gg
from app.player import GameInit, FingerGuessPlayTable, Player
from app.config import app

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get_tables_info():
    """
    获取 所有的牌桌信息列表
    :return: status: 牌桌开没开牌
    """
    assert isinstance(gg, GameInit)
    return [
        {
            'table_id': table_id, 'players': [p.id for p in table.players], 'status': True if table.game else False
        } for table_id, table in gg.table_dc
    ]


"""
各人的赌注、准备状态 都在随时变，不宜跟其它的一起返回
"""


@app.route('/api/table_info/')
def get_table_info():
    """
    获取 某一牌桌信息
    :return:  bet == -1 表示没下注
    """
    table_id = request.data
    assert isinstance(gg, GameInit)
    table = gg.table_dc.get(table_id)
    assert isinstance(table, FingerGuessPlayTable)

    return {
        'table_id': table_id,
        'status': True if table.game else False,
        'players': {
            p.id: {
                'nickname': p.nickname,
                'coins': p.coins
            }
            for p in table.players
        }
    }


class GetTablePlayerInfo(object):
    def __init__(self):
        pass

    @staticmethod
    def get_table_player_info(table_id, player_id):
        table = gg.table_dc.get(table_id)
        assert isinstance(table.game, GameInit)
        player_dc = table.players_cards_on_table.get(player_id)
        assert player_dc.get('player', Player)
        return player_dc

    def get_table_player_bet(self, table_id, player_id):
        player_dc = self.get_table_player_info(table_id, player_id)
        bet = player_dc.get('bet')
        return bet

    def get_table_player_ready(self, table_id, player_id):
        player_dc = self.get_table_player_info(table_id, player_id)
        ready = player_dc.get('ready')
        return ready


get_tp_info = GetTablePlayerInfo()


@app.route('/api/table_player_bet')
def get_table_player_bet():
    """
    获取牌桌上 玩家的下注
    :return:
    """
    info = request.data
    dc = json.loads(info)
    table_id, player_id = dc.get('table_id'), dc.get('player_id')
    bet = get_tp_info.get_table_player_bet(table_id, player_id)
    assert isinstance(bet, int)
    return bet


@app.route('/api/table_player_ready')
def get_table_player_ready():
    """
    获取牌桌上 玩家的准备状态
    :return:
    """
    info = request.data
    dc = json.loads(info)
    table_id, player_id = dc.get('table_id'), dc.get('player_id')
    ready = get_tp_info.get_table_player_bet(table_id, player_id)
    assert isinstance(ready, bool)
    return ready


# def get_game_info():
#     info = gg.panel()


# ----  查询 END  --------------------------------

# ----  更新 END  --------------------------------

@app.route('/api/set/player', methods=['POST'])
def set_player():
    info = request.data
    dc = json.loads(info)
    nickname = dc.get('nickname')
    set_player_queue.put((nickname, ))
    return True


@app.route('/api/add/player', methods=['POST'])
def gg_add_player():
    info = request.data
    dc = json.loads(info)
    player_id = dc.get('player_id')
    param = (player_id, )
    gg_add_player_queue.put(param)
    return True


@app.route('/api/add/player', methods=['POST'])
def table_add_player():
    info = request.data
    dc = json.loads(info)
    table_id, player_id = dc.get('table_id'), dc.get('player_id')
    param = (table_id, (player_id, ))
    add_player_queue.put(param)
    return True


if __name__ == '__main__':
    # get_game_info()
    pass
