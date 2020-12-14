from queue import Queue

from flask import Flask


class Constant(object):
    # 解包的格式
    CLIENT_QUERY_STUDY_LIST = None
    CLIENT_DEAD_NOTIFY = None
    CLIENT_UPLOAD_FAILED_NOTIFY = None
    CLIENT_UPLOAD_SUCCESS_NOTIFY = None
    CLIENT_QUERY_STUDY_LIST2 = None
    MINOR_VERSION = None
    MAJOR_VERSION = None
    METADATA_TYPE = None

    CLIENT_UPLOAD_FAILED_NOTIFY_RESP = None
    CLIENT_QUERY_STUDY_LIST_RESP = None
    CLIENT_QUERY_STUDY_LIST2_RESP = None
    CLIENT_UPLOAD_SUCCESS_NOTIFY_RESP = None
    CLIENT_DEAD_NOTIFY_RESP = None
    FMT_COMMON_HEAD = ''

    ACK_FAILED = 404
    ACK_SUCCESS = 200


# 命令字存放
command_str = {
    '': ''
}


app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False


class Config(object):
    users = [('xiaoY', '110')]

    src_id = None
    local_dispatcher_listen_port = None
    local_dispatcher_listen_ipv4 = None


# 为了复用这个处理线程，要求每个队列元素内容应该是 (id, data) 这种形式
gg_add_player_queue = Queue(maxsize=-1)
add_player_queue = Queue(maxsize=-1)
set_player_queue = Queue(maxsize=-1)
init_global_game_queue = Queue(maxsize=-1)
init_game_queue = Queue(maxsize=-1)
limit_guess_bid_queue = Queue(maxsize=-1)
limit_guess_put_queue = Queue(maxsize=-1)
card_queue = Queue(maxsize=-1)
