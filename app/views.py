import json
import os
import sys

from flask import request, jsonify

from app.bid import bid_limited_guessing
from app.config import set_player_queue, add_player_queue, init_global_game_queue, init_game_queue, \
    limit_guess_put_queue, limit_guess_bet_queue, limit_guess_ready_queue, limit_guess_settle_queue
from app.handler import HandlersInit
from app.log import logger
from app.player import GameInit, FingerGuessPlayTable, manager
from app.config import app

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# --- 启动
HandlersInit()


def error(msg='', code=400):
    """
    unexpected request receive
    :param msg: error msg
    :param code: 400
    :return: type json
    """
    ret = {
        'msg': msg,
        'code': code
    }
    return jsonify(ret)


def run(data=None, msg='', code=200):
    """
    expected(I doubt that) request
    :param data: payload (maybe null)
    :param msg: tell you what, for extending
    :param code: 200
    :return:
    """
    ret = {
        'data': data,
        'msg': msg,
        'code': code
    }
    return jsonify(ret)


# ----  启动 END  --------------------------------
@app.route('/api/init', methods=['POST'])
def global_game_init():
    """
    init global game
    :return:
    """
    try:
        info = request.data
        dc = json.loads(info)
        user, pwd = dc.get('user'), dc.get('password')
        init_global_game_queue.put((user, pwd))
        return run()
    except AssertionError as e:
        msg = 'TRY ME {}'.format(e)
        logger.error(msg)
        return error(msg)


# ----  启动 END  --------------------------------
@app.route('/api/table_list')
def get_tables_info():
    """
    获取 所有的牌桌信息列表
    :return: status: 牌桌开没开牌
    """
    assert isinstance(manager.gg, GameInit)
    data = [
        {
            'table_id': table_id, 'players': [p.id for p in table.players], 'status': True if table.game else False
        } for table_id, table in manager.gg.table_dc.items()
    ]
    return run(data=data)


"""
各人的赌注、准备状态 都在随时变，不宜跟其它的一起返回
"""


@app.route('/api/table_info')
def get_table_info():
    """
    获取 某一牌桌信息
    :return:  bet == -1 表示没下注
    """
    info = request.data
    table_id = json.loads(info).get('table_id')
    logger.info('gg: {}'.format(manager.gg))
    assert isinstance(manager.gg, GameInit)

    table = manager.gg.table_dc.get(table_id)
    assert isinstance(table, FingerGuessPlayTable)
    data = {
        'table_id': table_id,
        'status': True if table.game else False,
        'players': {
            p.id: {
                'nickname': p.name,
                'coins': p.coins
            }
            for p in table.players
        }
    }
    return run(data=data)


@app.route('/api/players_list')
def list_game_players():
    """
    获取 gg 所有player 信息
    :return:
    """
    assert isinstance(manager.gg, GameInit)
    data = [
        {
            "pid": player_id,
            "name": p.name
        }
        for player_id, p in manager.gg.player_info.items()
    ]
    return run(data=data)


class GetTablePlayerInfo(object):
    def __init__(self):
        pass

    @staticmethod
    def get_table_player_info(table_id, player_id):
        table = manager.gg.table_dc.get(table_id)
        player_dc = table.players_cards_on_table.get(player_id)
        return player_dc

    @staticmethod
    def get_table_player_stack(player_id):
        player = manager.gg.player_info.get(player_id)
        ls = [i.point for i in player.stack]
        return ls

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


@app.route('/api/table_player_stack')
def get_table_player_stack():
    """
    获取牌桌上 玩家的手牌
    :return:
    """
    info = request.data
    dc = json.loads(info)
    player_id = dc.get('player_id')
    data = get_tp_info.get_table_player_stack(player_id)

    return run(data=data)


@app.route('/api/table_player')
def get_table_player():
    """
    获取牌桌上， 玩家们出牌情况
    :return:
    """
    info = request.data
    dc = json.loads(info)
    player_id = dc.get('player_id')
    logger.info('<<< dc {}'.format(dc))
    assert player_id in manager.gg.player_info.keys()

    player = manager.gg.player_info.get(player_id)
    assert player.area
    table = player.area
    assert player in table.players
    put_dc = table.game.players_cards_on_table.get(player_id)
    assert put_dc is not None
    if table.game.winner is True:
        winner = True
    else:
        winner = table.game.winner.id if table.game.winner else None

    ret = {
        'player_id': player.id,
        'card_point': put_dc.get('card').point if put_dc.get('card') else None,
        'ready': put_dc.get('ready'),
        'bet': put_dc.get('bet'),
        'winner': winner
    }
    logger.info('{}'.format(table.game.players_cards_on_table))
    logger.info("<<<<<<<<< put_dc {}".format(ret))
    return run(data=ret)


# @app.route('/api/table_players/list')
# def get_table_players_info_dc():
#     """
#     获取牌桌上， 玩家们出牌情况
#     :return:
#     """
#     info = request.data
#     dc = json.loads(info)
#     table_id = dc.get('table_id')
#     assert table_id in manager.gg.table_dc.keys()
#
#     table = manager.gg.table_dc.get(table_id)
#     game = table.game
#     pass


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
    return run()


# @app.route('/api/add/player', methods=['POST'])
# def gg_add_player():
#     info = request.data
#     dc = json.loads(info)
#     player_id = dc.get('player_id')
#     param = (player_id, )
#     gg_add_player_queue.put(param)
#     return True


@app.route('/api/add/player', methods=['POST'])
def table_add_player():
    """
    牌桌增加玩家
    :return:
    """
    info = request.data
    dc = json.loads(info)
    table_id, player_id = dc.get('table_id'), dc.get('player_id')
    param = (table_id, (player_id, ))
    add_player_queue.put(param)
    return run()


@app.route('/api/init_game', methods=['POST'])
def init_game():
    info = request.data
    dc = json.loads(info)
    table_id = dc.get('table_id')
    param = (table_id, )
    init_game_queue.put(param)
    return run()


@app.route('/api/bid/limit_guess', methods=['POST'])
def limit_guess_bid():
    """
    发牌应该是 给游戏里的所有人发牌+发钱，那么导致一个结果，发牌后，不能再进人了
    :return:
    """
    # info = request.data
    # dc = json.loads(info)
    # table_id = dc.get('table_id')
    # param = table_id,
    # limit_guess_bid_queue.put(param)

    # TODO 待确认的逻辑

    players = manager.gg.player_info.values()
    for player in players:
        if player.stack or player.coins:
            continue
        else:
            bid_limited_guessing(player)
            player.deliver_coins(coin_num=3)
    return run()


@app.route('/api/put/limit_guess', methods=['POST'])
def limit_guess_put():
    info = request.data
    dc = json.loads(info)
    p_id, cards_point = dc.get('player_id'), dc.get('cards_point')   # 为了向后兼容，cp传列表
    param = p_id, cards_point
    limit_guess_put_queue.put(param)
    return run()


@app.route('/api/bet/limit_guess', methods=['POST'])
def limit_guess_bet():
    info = request.data
    dc = json.loads(info)
    p_id, coin_num = dc.get('player_id'), dc.get('coin_num')
    param = p_id, coin_num
    limit_guess_bet_queue.put(param)
    return run()


@app.route('/api/ready/limit_guess', methods=['POST'])
def limit_guess_ready():
    info = request.data
    dc = json.loads(info)
    p_id = dc.get('player_id')
    param = p_id,
    limit_guess_ready_queue.put(param)
    return run()


@app.route('/api/settle/limit_guess', methods=['POST'])
def limit_guess_settle():
    info = request.data
    dc = json.loads(info)
    p_id = dc.get('player_id')
    param = p_id,
    limit_guess_settle_queue.put(param)
    return run()


if __name__ == '__main__':
    # get_game_info()
    pass
