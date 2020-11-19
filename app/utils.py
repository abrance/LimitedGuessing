player_id_storage = [i for i in range(100)]
game_id_storage = [i for i in range(100)]


def get_player_id():
    """
    暂时就100，以后做一个自动获取最大id的队列
    :return: 最大player_id
    """
    return player_id_storage.pop(0)


def get_game_id():
    """
    获取赌局id
    """
    return game_id_storage.pop(0)
