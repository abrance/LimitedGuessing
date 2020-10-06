
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


class Config(object):
    src_id = None
    local_dispatcher_listen_port = None
    local_dispatcher_listen_ipv4 = None
