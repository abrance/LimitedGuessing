import queue

from app.log import logger

card_pool = queue.Queue(3*6)


class CardPool(object):
    def __init__(self):
        self.capacity = None
        pass


class Bid(object):
    """
    拥有牌库的一小部分牌
    作为一个发牌者的角色
    """
    def __init__(self):
        self.stack = None

    def set_stack(self, stack: list):
        self.stack = stack

    def bid(self, obj, limit=1):
        if not (isinstance(limit, int) and limit >= 0):
            raise Exception
        if not self.stack:
            raise Exception
        if not isinstance(obj.stack, list):
            raise Exception

        length = len(self.stack)
        if length < limit:
            raise Exception

        for i in range(limit):
            top = self.stack[0]
            self.stack = self.stack[1:]
            obj.hand_card(top)

        return True


class Card(object):
    """
    每一张牌应该设置只能一次赋值
    """
    colors = []
    points = []

    def __init__(self):
        self.color = None
        self.point = None

    def set_point(self, point: str):
        if self.point:
            raise Exception
        if point in self.points:
            self.point = point
        else:
            raise Exception

        return True

    def __str__(self):
        if self.point:
            return str(self.point)


class FingerGuessCard(Card):
    colors = []
    # 2020/10/5 rock-paper-scissors
    points = ['R', 'P', 'S']

    def __init__(self, **kwargs):
        super(FingerGuessCard, self).__init__()
        if 'point' in kwargs:
            self.set_point(kwargs.get('point'))

    # 2020/10/5 规则也放这里，可能比较好
    @classmethod
    def compare(cls, point1, point2):
        if point1 in cls.points and point2 in cls.points:
            pass
        else:
            logger.error('p1: {} p2: {}'.format(point1, point2))
            raise Exception

        if point1 == point2:
            return 0
        else:
            if 'R' in (point1, point2):
                return 'R' if 'S' in (point1, point2) else 'P'
            else:
                return 'S'


def bid_limited_guessing(player):
    """
    发牌逻辑 写简单一点
    :param player:
    :return:
    """
    # assert isinstance(player, Player)
    assert len(player.stack) == 0
    player.stack = [FingerGuessCard(point=p) for p in FingerGuessCard.points for _ in range(3)]
