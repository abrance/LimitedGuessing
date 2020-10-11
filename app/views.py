
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.player import g


def get_game_info():
    info = g.panel()


if __name__ == '__main__':
    get_game_info()
