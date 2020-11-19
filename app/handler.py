import time
from queue import Queue
from threading import Thread

from app.config import add_player_queue, set_player_queue, init_global_game_queue, Config
from app.log import logger
from app.player import Player, GameInit
from app.utils import get_player_id


gg = None


class Handler(Thread):
    """
    采用队列方式来 进行通信，handler应该才是真正进行处理信息的角色
    """
    def __init__(self, _queue):
        super(Handler, self).__init__()
        assert isinstance(_queue, Queue)
        self.queue = _queue

    def handle(self):
        """
        子类需实现这部分代码，对消息队列进行处理
        :return: None
        """
        pass

    def run(self) -> None:
        while True:
            if self.queue.qsize():
                self.handle()
            else:
                time.sleep(0.1)


class InitGlobalGameHandler(Handler):
    """
    开始全局的游戏
    """
    def __init__(self):
        super(InitGlobalGameHandler, self).__init__(init_global_game_queue)

    def handle(self):
        param = self.queue.get()
        host, password = param

        global gg
        if isinstance(gg, GameInit):
            return True
        else:
            if (host, password) in Config.users:
                gg = GameInit()
                return True
            else:
                logger.error('not administrator')
                return False


class SetPlayerHandler(Handler):
    """
    新增玩家 Handler， 目标队列： set_player_queue
    """
    def __init__(self):
        super(SetPlayerHandler, self).__init__(set_player_queue)

    def handle(self):
        # set_player_queue 元素 data: (nickname, )
        param = self.queue.get()
        nickname, = param

        new_player_id = get_player_id()
        new_player = Player()
        new_player.set_name(nickname)
        new_player.set_id(new_player_id)

        gg.add_player(new_player)



class AddPlayerHandler(Handler):
    """
    玩家加入牌桌 Handler， 目标队列：
    """
    def __init__(self):
        super(AddPlayerHandler, self).__init__(add_player_queue)

    def handle(self):
        # add_player_queue 元素 (table_id, data)
        # data: (player_id, )
        param = self.queue.get()
        table_id, data = param
        player_id, = data
        try:
            assert isinstance(gg, GameInit)
            assert table_id in gg.table_dc.keys()
            assert player_id in gg.player_info.keys()
            table = gg.table_dc[table_id]
            player = gg.player_info[player_id]
            assert player not in table.players
            table.add_player(player)
            return True
        except AssertionError as e:
            logger.error('AddPlayerHandler fail: {}'.format(e))
            return False
