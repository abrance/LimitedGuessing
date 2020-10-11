from threading import Thread
import time


class PlayTable(object):
    def __init__(self):
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

    def add_player(self, pid):
        if len(self.players) < self.capacity:
            pass
        else:
            raise Exception

        self.players.append(pid)
        return True


class FingerGuessPlayTable(PlayTable):
    def __init__(self):
        super(FingerGuessPlayTable, self).__init__()
        self.capacity = 2


class Player(object):
    def __init__(self):
        self.name = None
        self.id = None
        self.stack = []

    def set_name(self, name: str):
        self.name = name

    def set_id(self, pid: int):
        self.id = pid

    def hand_card(self, card):
        self.stack.append(card)

    def __str__(self):
        return str(self.id)


"""
游戏需要有管理员
"""


class GameInit(Thread):
    def __init__(self):
        super(GameInit, self).__init__()
        self.table_cnt = 10
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
    # p1 = Player()
    # p1.set_id(1)
    # p2 = Player()
    # p2.set_id(2)
    # g.add_player(p1)
    # g.add_player(p2)
    # print([i.__dict__ for i in g.player_info.values()])
    

            
if __name__ == '__main__':
    pass
