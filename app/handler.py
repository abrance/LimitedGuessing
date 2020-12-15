import time
from queue import Queue
from threading import Thread

from app.config import add_player_queue, set_player_queue, init_global_game_queue, Config, init_game_queue, \
    limit_guess_put_queue, limit_guess_bet_queue, limit_guess_ready_queue, limit_guess_settle_queue
from app.log import logger
from app.player import Player, GameInit, manager
from app.utils import get_player_id


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
                time.sleep(1)


class InitGlobalGameHandler(Handler):
    """
    开始全局的游戏
    """
    def __init__(self):
        super(InitGlobalGameHandler, self).__init__(init_global_game_queue)

    def handle(self):
        param = self.queue.get()
        host, password = param

        if isinstance(manager.gg, GameInit):
            return True
        else:
            if (host, password) in Config.users:
                manager.turn_on()
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
        if nickname in [i.name for i in manager.gg.player_info.values()]:
            pass
        else:
            new_player = Player()
            new_player.set_name(nickname)
            new_player.set_id(new_player_id)

            manager.gg.add_player(new_player)


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
            logger.info(manager.gg)
            logger.info(manager.gg.table_dc)
            assert isinstance(manager.gg, GameInit)
            assert table_id in manager.gg.table_dc.keys()
            assert player_id in manager.gg.player_info.keys()
            table = manager.gg.table_dc[table_id]
            player = manager.gg.player_info[player_id]
            if player not in table.players:
                table.add_player(player)
            return True
        except AssertionError as e:
            logger.error('AddPlayerHandler fail: {}'.format(e))
            return False


class InitGameHandler(Handler):
    """
    人数齐了，游戏就可以开了
    """
    def __init__(self):
        super(InitGameHandler, self).__init__(init_game_queue)

    def handle(self):
        param = self.queue.get()
        table_id, = param
        try:
            assert isinstance(manager.gg, GameInit)
            assert table_id in manager.gg.table_dc.keys()
            table = manager.gg.table_dc[table_id]
            table.init_gambling()
            return True
        except AssertionError as e:
            logger.error('InitGameHandler fail: {}'.format(e))
            return False


class LimitedGuessPutHandler(Handler):
    """
    出牌队列
    """
    def __init__(self):
        super(LimitedGuessPutHandler, self).__init__(limit_guess_put_queue)

    def handle(self):
        param = self.queue.get()
        p_id, card_points = param
        logger.info('<<<<< p_id: {} card_points: {}'.format(p_id, card_points))
        try:
            assert isinstance(manager.gg, GameInit)
            assert p_id in manager.gg.player_info.keys()
            assert type(card_points) is list and len(card_points) == 1

            player = manager.gg.player_info[p_id]

            table = player.area
            table.game.put(player, card_points[0])

            return True
        except AssertionError as e:
            logger.error('LimitedGuessPutHandler fail: {}'.format(e))
            return False


class LimitedGuessBetHandler(Handler):
    """
    下注 处理
    """
    def __init__(self):
        super(LimitedGuessBetHandler, self).__init__(limit_guess_bet_queue)

    def handle(self):
        param = self.queue.get()
        p_id, coin_num = param
        logger.info('<<<<< p_id: {} coin_num: {}'.format(p_id, coin_num))
        try:
            assert isinstance(manager.gg, GameInit)
            assert p_id in manager.gg.player_info.keys()
            assert type(coin_num) is int and coin_num >= 1
            player = manager.gg.player_info[p_id]

            table = player.area
            table.game.bet(player, coin_num)
            return True
        except AssertionError as e:
            logger.error('LimitedGuessBetHandler fail: {}'.format(e))
            return False


class LimitedGuessReadyHandler(Handler):
    """
    玩家准备好了 确认赌局成立处理
    """
    def __init__(self):
        super(LimitedGuessReadyHandler, self).__init__(limit_guess_ready_queue)

    def handle(self):
        param = self.queue.get()
        p_id, = param
        logger.info('<<<<< p_id: {}'.format(p_id))
        try:
            assert isinstance(manager.gg, GameInit)
            assert p_id in manager.gg.player_info.keys()
            player = manager.gg.player_info[p_id]

            table = player.area
            ret = table.game.ready(player)

            return True
        except AssertionError as e:
            logger.error('LimitedGuessReadyHandler fail: {}'.format(e))
            return False


class LimitedGuessSettleHandler(Handler):
    """
    游戏结算 处理
    每一个玩家都可以单独结算
    """
    def __init__(self):
        super(LimitedGuessSettleHandler, self).__init__(limit_guess_settle_queue)

    def handle(self):
        param = self.queue.get()
        p_id, = param
        logger.info('<<<<< p_id: {}'.format(p_id))
        try:
            assert isinstance(manager.gg, GameInit)
            assert p_id in manager.gg.player_info.keys()
            player = manager.gg.player_info[p_id]

            table = player.area
            ret = table.game.settle(player, table=False)

            logger.info('succeed {}'.format(ret))
            return True
        except AssertionError as e:
            logger.error('LimitedGuessSettleHandler fail: {}'.format(e))
            return False


class HandlersInit(object):
    """
    init all handlers
    """
    init_ggh = InitGlobalGameHandler()
    sph = SetPlayerHandler()
    aph = AddPlayerHandler()
    igh = InitGameHandler()
    ph = LimitedGuessPutHandler()
    bh = LimitedGuessBetHandler()
    rh = LimitedGuessReadyHandler()
    sh = LimitedGuessSettleHandler()
    init_ggh.start()
    sph.start()
    aph.start()
    igh.start()
    ph.start()
    bh.start()
    rh.start()
    sh.start()
