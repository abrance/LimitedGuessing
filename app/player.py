from datetime import datetime
from threading import Thread
import time

from app.bid import Card, FingerGuessCard
from app.utils import get_game_id


class LimitedGuessing(object):
    """
    桌号确定，人数一齐，开始游戏，所以玩家列表必传
    """
    def __init__(self, table_id, players: list):
        assert table_id in g.table_dc.keys()
        assert len(players) == 2
        self.game_id = get_game_id()
        self.table_id = table_id
        self.players = players
        self.players_cards_on_table = []
        self.winner = None

    def bid(self):
        """
        发牌
        :return: None
        """
        pass

    def put(self, player, card):
        assert isinstance(player, Player) and isinstance(card, Card)
        assert player in self.players
        put_dc = {
            'player': player,
            'card': card,
            'time': datetime.now()
        }

        # 每一张牌都应该是由一个位置转到另一个位置的，这里是玩家手中出到牌桌
        player.play(card)
        self.players_cards_on_table.append(put_dc)

    def check(self):
        assert len(self.players_cards_on_table) > 0
        f = self.players_cards_on_table[0]
        s = self.players_cards_on_table[1]
        f_card = f.get('card')
        s_card = s.get('card')
        ret = FingerGuessCard.compare(f_card, s_card)
        if isinstance(ret, int):
            # 平局
            return True
        else:
            if f_card == ret:
                self.winner = f.get('player')
                return f.get('player')
            else:
                self.winner = s.get('player')
                return s.get('player')


class PlayTable(object):
    def __init__(self):
        self.game = None
        self.table_id = None
        self.capacity = 0
        self.players = []

    def set_table_id(self, table_id: int):
        if isinstance(table_id, int):
            self.table_id = table_id
        else:
            raise Exception
        return True

    def set_capacity(self, capacity):
        if isinstance(capacity, int) and capacity > 0:
            pass
        else:
            raise Exception

        self.capacity = capacity
        return True

    def add_player(self, player):
        assert len(self.players) < self.capacity
        self.players.append(player)
        return True

    def init_gambling(self):
        game = LimitedGuessing(self.table_id, self.players)
        self.game = game

    def close(self):
        self.game = None
        self.players = []


class FingerGuessPlayTable(PlayTable):
    def __init__(self):
        super(FingerGuessPlayTable, self).__init__()
        self.capacity = 2


class Player(object):
    def __init__(self):
        self.name = None
        self.id = None
        self.stack = []
        self.create_time = datetime.now()

    def set_name(self, name: str):
        self.name = name

    def set_id(self, pid: int):
        self.id = pid

    def hand_card(self, card):
        self.stack.append(card)

    def play(self, card):
        assert card in self.stack
        self.stack.remove(card)

    def __str__(self):
        return str(self.id)


"""
游戏需要有管理员
"""


class GameInit(Thread):
    def __init__(self):
        super(GameInit, self).__init__()
        self.table_cnt = 1
        self.table_dc = {}
        self.game_info = {}
        self.player_info = {}

        self.table()
        self.panel()
        # self.run()

    def table(self):
        for i in range(self.table_cnt):
            t = FingerGuessPlayTable()
            t.set_table_id(i)
            self.table_dc.__setitem__(t.table_id, t)

    def panel(self):
        self.game_info.__setitem__('table_dc', [i.__dict__ for i in self.table_dc.values()])
        self.game_info.__setitem__('player_info', [i.__dict__ for i in self.player_info.values()])
        print(self.game_info)
        return self.game_info

    def add_player(self, player):
        if player.id not in self.player_info:
            self.player_info.__setitem__(player.id, player)
 
    def run(self) -> None:
        while True:
            time.sleep(5)
            self.panel()


g = GameInit()


def main():
    p1 = Player()
    p1.set_id(1)
    p1.set_name('xiaoY')
    p2 = Player()
    p2.set_id(2)
    p2.set_name('fei')
    g.add_player(p1)
    g.add_player(p2)
    print([i.__dict__ for i in g.player_info.values()])
    

if __name__ == '__main__':
    main()
