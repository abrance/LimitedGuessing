
import os
import sys

from app.handler import gg
from app.player import GameInit

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get_tables_info():
    """
    获取 所有的牌桌信息列表
    :return:
    """
    assert isinstance(gg, GameInit)
    return [
        {
            'table_id': table_id, 'players': table.players, 'status': True if table.game else False
        } for table_id, table in gg.table_dc
    ]


def get_game_info():
    info = gg.panel()


if __name__ == '__main__':
    get_game_info()
