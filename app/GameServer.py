#!/usr/bin/python3
# -*- coding: utf-8 -*-

import selectors
import socket
import struct
import time
import json
import sys

import config
import utils
import connection
import message
import models

from log import logger

class Dispatcher():

    def __init__(self):
        # fesock: frontend socket，用于给前面的客户端连接的监听套接字
        self.fesock = None

        # besock: backend socket，用于给后面的工作者连接的监听套接字
        self.besock = None

        # hbsock: heartbeat socket，用于给监控服务发送心跳消息
        self.hbsock = None

        # 记录下所有的消息序号对应的连接。主要是为了在收到工作者的响应
        # 时，能够找到对应的客户端
        self.feclis = {}

        # 记录下本进程的消息计数和收到的客户端消息 trans_id 的对应关系，
        # 主要为了在收到工作者的响应时，能够正确填充保存下来的 trans_id
        self.trans_ids = {}

        # 记录下所有的客户端已连接套接字。以套接字为键，可以查找到对应的连接上下
        # 文，用于在一个消息没有完整地接收或者发送时，记录下一次要接收或者发送的
        # 数据
        self.feconns = {}

        # 记录下所有的后端工作者已连接套接字。由于分发者和工作者是在同一个节点，
        # 不能一次接收或者发送完整数据的可能性不大。
        self.beconns = {}
        self.bequerylru = []
        self.bealterlru = []

        # 用于监测所有的套接字，包括监听套接字和连接套接字
        self.selector = selectors.DefaultSelector()

        # 存放客户端连接的更新数据的消息类型发送到的后端工作者
        # 这个结构的一个可能的取值：self.msg_on_worker[cliconn][CLIENT_UPLOAD] = workconn
        self.msg_on_worker = {}

        # 记录从所有客户端收到的消息序号
        self.msg_seq = 0

    def get_lru_worker(self, lrulist):
        if len(lrulist) > 0:
            worker_sock = lrulist.pop(0)
            lrulist.append(worker_sock)
            return worker_sock
        else:
            return None

    def record_msg_on_worker(self, clisock, worker_sock):
        keyid = id(clisock)
        self.msg_on_worker[keyid] = {}
        self.msg_on_worker[keyid][config.Constant.CLIENT_UPLOAD] = worker_sock
        self.msg_on_worker[keyid][config.Constant.CLIENT_DEL] = worker_sock

    def remove_msg_on_worker(self, clisock):
        keyid = id(clisock)
        if keyid in self.msg_on_worker.keys():
            del self.msg_on_worker[keyid][config.Constant.CLIENT_UPLOAD]
            del self.msg_on_worker[keyid][config.Constant.CLIENT_DEL]
            del self.msg_on_worker[keyid]
            logger.debug("remove alter worker from client socket {}".format(keyid))
        else:
            pass

    def select_worker(self, clisock, msgtype):
        """根据客户端连接的消息类型，选择合适的后端工作者
        客户端发起的对于数据的更新请求，为了保证处理上的简单性和正确性，应该将这
        种类型的消息发送到同一个后端工作者
        如果没有后端工作者，则返回 None
        """
        keyid = id(clisock)
        if msgtype in [config.Constant.CLIENT_UPLOAD, config.Constant.CLIENT_DEL]:
            if (    (keyid in self.msg_on_worker.keys())
                and (msgtype in self.msg_on_worker[keyid].keys())):

                return self.msg_on_worker[keyid][msgtype]
            else:
                worker_sock = self.get_lru_worker(self.bealterlru)
                if worker_sock is None:
                    return None
                else:
                    self.record_msg_on_worker(clisock, worker_sock)
                    return worker_sock
        else:
            return self.get_lru_worker(self.bequerylru)

    def recv_from_client(self, sock):
        """从客户端接收数据，转发到工作者处理
        这个函数能够处理数据没有完整发送的情况"""

        # 定义一些只在这个函数里面使用的嵌套函数，希望能够使代码读起来清晰一点

        def recv_from_client_prepare(self, sock):
            if id(sock) not in self.feconns.keys():
                connctx = connection.ConnectionContext(clisock=sock)
                logger.debug("> create socket {0} connection context {1}".format(id(sock), connctx))
                self.feconns[id(sock)] = connctx
                logger.debug("> save socket {0} connection context".format(id(sock)))
            else:
                connctx = self.feconns[id(sock)]
                logger.debug("> retrive socket {0} connection context".format(id(sock)))

            if connctx.recvstate == connection.CONN_RECV_DONE:
                connctx.recvstate = connection.CONN_RECV_HEAD
                connctx.recvleft = config.Constant.HEAD_LENGTH

            return connctx

        def handle_recv_done(self, connctx):
            header_pack = connctx.recvbuf[:config.Constant.HEAD_LENGTH]
            header_unpack = struct.unpack(config.Constant.FMT_COMMON_HEAD, header_pack)
            connctx.nodeid = client_src_id = header_unpack[5]

            # 将消息包头部的 trans_id 用作消息的返回标识。因为
            # trans_id 是 8 个字节 64 位，足够存放下 id(clisock)。从
            # worker 接收到的响应消息，根据本节点对客户端的消息计数，
            # 找到对于的 clisock 的连接上下文 clictx。而在 clisock 被
            # 关闭时，清空这个客户端连接已发送到后端 worker 处理，但是
            # 没有收到响应的消息序号。总的映射关系如下：
            #
            # message sequence -> client socket -> client socket context
            # message sequence -> client transaction id
            # client socket -> message sequence
            self.trans_ids[self.msg_seq] = trans_id = header_unpack[7]
            h = message.Header()
            h.total_size = header_unpack[0]
            h.major      = header_unpack[1]
            h.minor      = header_unpack[2]
            h.src_type   = header_unpack[3]
            h.dst_type   = header_unpack[4]
            h.src_id     = header_unpack[5]
            h.dst_id     = header_unpack[6]
            h.tranid     = self.msg_seq # header_unpack[7]
            h.sequence   = header_unpack[8]
            h.command    = header_unpack[9]
            h.ack_code   = header_unpack[10]
            h.total      = header_unpack[11]
            h.offset     = header_unpack[12]
            h.count      = header_unpack[13]
            header_pack2 = h.pack()

            logger.debug("> change client socket {} trans_id: {} -> {}".format(
                id(connctx.clisock), trans_id, self.msg_seq
            ))

            connctx.msg_seqs.append(self.msg_seq)
            self.feclis[self.msg_seq] = connctx.clisock

            self.msg_seq = self.msg_seq + 1

            # 选择一个工作者，将接收到的完整消息发送到这个后端工作者。同一个
            # 客户端的所有对数据更改的请求，以后都发送到这个选定的工作者中
            while True:
                worker_sock = self.select_worker(connctx.clisock, connctx.type)
                if id(worker_sock) in self.beconns.keys():
                    workctx = self.beconns[id(worker_sock)]
                    workctx.sendbuf =   workctx.sendbuf \
                                      + header_pack2 \
                                      + connctx.recvbuf[config.Constant.HEAD_LENGTH:]
                    workctx.sendleft = len(workctx.sendbuf)
                    logger.debug("> copy whole message to worker send buffer")

                    # 接收完一条完整的消息之后，清空客户端连接的接收缓冲区，等
                    # 待接收下一条消息。如果不清空，就会发送重复的消息到后端的
                    # 工作者。
                    connctx.recvbuf = b''
                    connctx.recvleft = 0
                    logger.debug("> empty socket {} recvbuf".format(id(connctx.clisock)))

                    self.selector.modify(
                        worker_sock,
                        selectors.EVENT_READ | selectors.EVENT_WRITE,
                        self.worker_read_write
                    )
                    logger.debug("monitor EVENT_READ|EVENT_WRITE on worker socket {}".format(
                        id(worker_sock)
                    ))
                    break
                else:
                    if worker_sock is None:
                        logger.error("no worker to handle request")
                        break
                    else:
                        logger.error("invalid worker socket {}".format(id(worker_sock)))
                        self.remove_msg_on_worker(connctx.clisock)

        def handle_recv_header(self, connctx, data):
            logger.debug("> receive header completed")
            connctx.recvleft = 0
            connctx.recvbuf = connctx.recvbuf + data
            head_unpack = struct.unpack(config.Constant.FMT_COMMON_HEAD, connctx.recvbuf)
            total_size = head_unpack[0]
            connctx.recvleft = total_size - struct.calcsize(config.Constant.FMT_COMMON_HEAD)
            connctx.recvstate = connection.CONN_RECV_BODY
            connctx.type = head_unpack[9]
            if connctx.recvleft > 0:
                logger.debug("has {0} bytes body left, wait next time to recv".format(connctx.recvleft))
                connctx.recvstate = connection.CONN_RECV_BODY
            elif connctx.recvleft == 0:
                logger.debug("recv message completed, no body left")
                connctx.recvstate = connection.CONN_RECV_DONE
                handle_recv_done(self, connctx)
            else:
                logger.error("corrupt header: message length {0} bytes < header fixed length {1} bytes".format(
                    connctx.recvleft, struct.calcsize(config.Constant.FMT_COMMON_HEAD)))
                self.client_cleanup(connctx.clisock)

        def handle_recv_body(self, connctx, data):
            logger.debug("> receive body completed")
            connctx.recvstate = connection.CONN_RECV_DONE
            connctx.recvleft = 0
            connctx.recvbuf = connctx.recvbuf + data
            handle_recv_done(self, connctx)

        def handle_peer_close(self, connctx):
            self.client_cleanup(connctx.clisock)

        def handle_recv_partial(self, connctx, data):
            connctx.recvleft = connctx.recvleft - len(data)
            connctx.recvbuf = connctx.recvbuf + data
            logger.debug("> {0} bytes left, wait for next time to recv".format(connctx.recvleft))

        # 在这里开始真正的处理

        logger.debug("prepare to handle client socket {0}".format(id(sock)))

        connctx = recv_from_client_prepare(self, sock)
        recvlen, data = utils.attempt_recvall(sock, connctx.recvleft)
        assert recvlen <= connctx.recvleft

        logger.debug("> receive {0} bytes".format(recvlen))

        if recvlen == connctx.recvleft:
            # 接收到完整的消息头部，根据头部指示的长度，继续接收消息体
            if connctx.recvstate == connection.CONN_RECV_HEAD:
                handle_recv_header(self, connctx, data)
            else: # connctx.recvstate == connection.CONN_RECV_BODY
                handle_recv_body(self, connctx, data)
        elif recvlen == 0:
            # 客户端关闭了连接，本端取消接收，同时销毁连接上下文
            handle_peer_close(self, connctx)
        else: # recvlen < connctx.recvleft
            # 本次接收尚未接收完整的数据，等待下次继续接收
            handle_recv_partial(self, connctx, data)

    def send_to_client(self, sock):
        clictx = self.feconns[id(sock)]
        if clictx.sendleft > 0:
            try:
                sendlen = sock.send(clictx.sendbuf)
            except Exception as e:
                logger.error("socket {0} trigger exception: {1}".format(
                    id(sock), e
                ))
                self.client_cleanup(sock)
            else:
                logger.debug("> send {0} bytes to client socket {1}".format(sendlen, id(sock)))
                if sendlen == clictx.sendleft:
                    clictx.sendbuf = b''
                    clictx.sendleft = 0
                    self.selector.modify(sock, selectors.EVENT_READ, self.client_read_write)
                    logger.debug("> send completed, monitor EVENT_READ on client socket {0}".format(id(sock)))
                elif sendlen == 0:
                    self.client_cleanup(sock)
                else:
                    clictx.sendleft = clictx.sendleft - sendlen
                    clictx.sendbuf = clictx.sendbuf[sendlen:]
                    logger.debug("> {0} bytes left, wait for next time to send".format(clictx.sendleft))
        else:
            if clictx.sendleft < 0:
                logger.warning("invalid sendleft:{0} on client socket {1}".format(clictx.sendleft, id(sock)))
                self.client_cleanup(sock)
            else: # clictx.sendleft == 0
                logger.warning("has no data send to client socket {0} for now".format(id(sock)))
                self.selector.modify(sock, selectors.EVENT_READ, self.client_read_write)
                logger.debug("> monitor EVENT_READ on client socket {0}".format(id(sock)))

    def client_read_write(self, sock, event):
        if (event & selectors.EVENT_READ):
            self.recv_from_client(sock)
        else:
            # 没有可读事件，继续处理
            pass

        # sock 可能已被关闭，对应的上下可能被销毁；需要处理这种情况
        if (event & selectors.EVENT_WRITE):
            if id(sock) in self.feconns.keys():
                self.send_to_client(sock)
            else:
                logger.debug("client socket {0} was closed, left EVENT_WRITE unhandled".format(id(sock)))
        else:
            # 没有可写事件，继续处理
            pass

        if (event & ~(selectors.EVENT_READ | selectors.EVENT_WRITE)):
            logger.error("catch unknown event {0}".format(event))
            self.client_cleanup(sock)
        else:
            # 读写事件已经处理过了
            pass

    def accept_client(self, sock, event):
        conn, addr = sock.accept()
        conn.setblocking(False)
        logger.debug("> accept client socket {0}, {1}".format(id(conn), conn))

        self.feconns[id(conn)] = connection.ConnectionContext(clisock=conn)
        logger.debug("> create client socket {0} connection context".format(id(conn)))

        self.selector.register(conn, selectors.EVENT_READ, self.client_read_write)
        logger.debug("> register EVENT_READ for client socket {0}".format(id(conn)))

    def cleanup(self, sock):
        self.selector.unregister(sock)
        sock.close()

    def client_cleanup(self, sock):
        if id(sock) in self.feconns.keys():
            clictx = self.feconns[id(sock)]
            clictx.clisock = None
            for seq in clictx.msg_seqs:
                if seq in self.feclis.keys():
                    del self.feclis[seq]
            del clictx
            del self.feconns[id(sock)]
            self.cleanup(sock)
            logger.debug("client socket {} closed, cleanup".format(id(sock)))

    def worker_cleanup(self, sock):
        try:
            self.bequerylru.remove(sock)
            self.bealterlru.remove(sock)
        except ValueError as e:
            pass
        if id(sock) in self.beconns.keys():
            wrkctx = self.beconns[id(sock)]
            wrkctx.clisock = None
            del wrkctx
            del self.beconns[id(sock)]
            self.cleanup(sock)
            logger.debug("worker socket {} cleanup".format(id(sock)))
        else:
            logger.debug("no worker socket {} in beconns".format(id(sock)))

    def recv_from_worker(self, sock):
        def handle_recv_from_worker_done(self, connctx):
            # 找到客户端的连接，将从工作者收到的数据转发到客户端连接的发送缓
            # 冲区中，等待客户端连接可写时，将数据发送给客户端
            header_pack = connctx.recvbuf[:config.Constant.HEAD_LENGTH]
            header_unpack = struct.unpack(config.Constant.FMT_COMMON_HEAD, header_pack)
            msg_seq = header_unpack[7]
            if msg_seq in self.feclis.keys():
                clisock = self.feclis[msg_seq]
                clictx = self.feconns[id(clisock)]

                h = message.Header()
                h.total_size = header_unpack[0]
                h.major      = header_unpack[1]
                h.minor      = header_unpack[2]
                h.src_type   = header_unpack[3]
                h.dst_type   = header_unpack[4]
                h.src_id     = header_unpack[5]
                h.dst_id     = header_unpack[6]
                h.tranid     = self.trans_ids[msg_seq] # header_unpack[7]
                h.sequence   = header_unpack[8]
                h.command    = header_unpack[9]
                h.ack_code   = header_unpack[10]
                h.total      = header_unpack[11]
                h.offset     = header_unpack[12]
                h.count      = header_unpack[13]

                header_pack2 = h.pack()
                clictx.sendbuf =   clictx.sendbuf \
                                 + header_pack2 \
                                 + connctx.recvbuf[config.Constant.HEAD_LENGTH:]
                clictx.sendleft = len(clictx.sendbuf)
                connctx.recvbuf = b''
                logger.debug("> copy data to client send buffer completed")
                self.selector.modify(clisock, selectors.EVENT_READ | selectors.EVENT_WRITE,
                                     self.client_read_write)
                logger.debug("> monitor EVENT_READ|EVENT_WRITE on client socket {0}".format(
                    id(clisock)))
            else:
                logger.warning(
                    "drop responsed message {}: client already closed".format(
                    msg_seq
                ))
                connctx.recvbuf = b''

        connctx = self.beconns[id(sock)]
        if connctx.recvstate == connection.CONN_RECV_DONE:
            connctx.recvstate = connection.CONN_RECV_HEAD
            connctx.recvleft = config.Constant.HEAD_LENGTH

        recvlen, data = utils.attempt_recvall(sock, connctx.recvleft)
        assert recvlen <= connctx.recvleft

        logger.debug("> receive {0} bytes".format(recvlen))

        if recvlen == 0:
            # 对端关闭了连接，本端取消接收，同时销毁连接
            logger.debug("worker closed socket {0}".format(id(sock)))
            self.worker_cleanup(sock)
        elif recvlen == connctx.recvleft:
            # 接收到完整的消息头部，根据头部指示的长度，继续接收消息体的内容
            if connctx.recvstate == connection.CONN_RECV_HEAD:
                logger.debug("> receive header completed")
                connctx.recvbuf = connctx.recvbuf + data
                head_unpack = struct.unpack(config.Constant.FMT_COMMON_HEAD, data)
                total_size = head_unpack[0]
                connctx.recvleft = total_size - struct.calcsize(config.Constant.FMT_COMMON_HEAD)
                if connctx.recvleft > 0:
                    logger.debug("has {0} bytes body left, wait next time to recv".format(connctx.recvleft))
                    connctx.recvstate = connection.CONN_RECV_BODY
                elif connctx.recvleft == 0:
                    logger.debug("recv message completed, no body left")
                    connctx.recvstate = connection.CONN_RECV_DONE
                    handle_recv_from_worker_done(self, connctx)
                else:
                    logger.error("corrupt header: message length {0} bytes < fixed header length {1} bytes".format(
                        connctx.recvleft, struct.calcsize(config.Constant.FMT_COMMON_HEAD)))
                    self.worker_cleanup(sock)
            else: # connctx.recvstate == connection.CONN_RECV_BODY
                logger.debug("> receive body completed")
                connctx.recvstate = connection.CONN_RECV_DONE
                connctx.recvleft = 0
                connctx.recvbuf = connctx.recvbuf + data
                handle_recv_from_worker_done(self, connctx)
        else: # recvlen < connctx.recvleft
            # 本次没有接收到希望接收的长度，等待下次继续接收
            connctx.recvbuf = connctx.recvbuf + data
            connctx.recvleft = connctx.recvleft - recvlen
            logger.debug("> {0} bytes left, wait for next time to read".format(connctx.recvleft))

    def send_to_worker(self, sock):
        workctx = self.beconns[id(sock)]
        if workctx.sendleft > 0:
            sendlen = sock.send(workctx.sendbuf)
            logger.debug("> send {0} bytes on worker socket {1}".format(sendlen, id(sock)))
            if sendlen == workctx.sendleft:
                workctx.sendbuf = b''
                workctx.sendleft = 0
                self.selector.modify(sock, selectors.EVENT_READ, self.worker_read_write)
                logger.debug("> send completed, monitor EVENT_READ on worker socket {0}".format(id(sock)))
            elif sendlen == 0:
                self.worker_cleanup(sock)
            else:
                workctx.sendleft = workctx.sendleft - sendlen
                workctx.sendbuf = workctx.sendbuf[sendlen:]
                logger.debug("> {0} bytes left, wait for next time to send".format(workctx.sendleft))
        else:
            if workctx.sendleft < 0:
                logger.warning("invalid sendleft:{0} on worker socket {1}".format(workctx.sendleft, sock))
                self.worker_cleanup(sock)
            else:
                logger.debug("no data send to worker socket {0}".format(sock))
                self.selectors.modify(sock, selectors.EVENT_READ, self.worker_read_write)
                logger.debug("> monitor EVENT_READ on worker socket {0}".format(id(sock)))

    def worker_read_write(self, sock, event):
        if (event & selectors.EVENT_READ):
            self.recv_from_worker(sock)
        else:
            # 没有可读事件，继续处理
            pass

        # sock 可能已被关闭，对应的上下可能被销毁；需要处理这种情况
        if (event & selectors.EVENT_WRITE):
            if id(sock) in self.beconns.keys():
                self.send_to_worker(sock)
            else:
                logger.debug("worker socket {0} was closed, left EVENT_WRITE unhandled".format(id(sock)))
        else:
            # 没有可写事件，继续处理
            pass

        if (event & ~(selectors.EVENT_READ | selectors.EVENT_WRITE)):
            # 没有收到读写事件，但收到了其他的未知事件，关闭 sock
            logger.error("catch unknown event {0}".format(event))
            if id(sock) in self.beconns[id(sock)]:
                self.worker_cleanup(sock)
            else:
                logger.debug("worker socket {0} not in beconns".format(id(sock)))
                self.cleanup(sock)
        else:
            # 读写事件已经处理过了
            pass

    def accept_worker(self, sock, event):
        conn, addr = sock.accept()
        conn.setblocking(False)
        logger.info("> accept worker socket {0}, {1}".format(id(conn), conn))

        self.beconns[id(conn)] = connection.ConnectionContext(clisock=conn)
        self.bequerylru.append(conn)
        self.bealterlru.append(conn)
        logger.debug("> save worker socket {0}, connctx, bequerylru, bealterlru".format(id(conn)))

        self.selector.register(conn, selectors.EVENT_READ, self.worker_read_write)
        logger.debug("> register worker socket {0}".format(id(conn)))

    def setup(self):
        # 首先连接数据库，如果数据库连接失败，则初始化失败
        db = models.Database()
        try:
            db.create_tables()
        except Exception as e:
            logger.error("database initialize failed")
            logger.error("Exception: {}".format(e))
            sys.exit(-1)
        else:
            # 创建数据库表成功，继续往下执行
            pass

        self.selector = selectors.DefaultSelector()

        self.fesock = utils.create_server_socket(
            config.Config.local_listen_ipv4,
            config.Config.local_listen_port)
        self.selector.register(self.fesock, selectors.EVENT_READ, self.accept_client)
        logger.debug("> register client listen socket {0}".format(id(self.fesock)))

        self.besock = utils.create_server_socket(
            config.Config.local_dispatcher_listen_ipv4,
            config.Config.local_dispatcher_listen_port)
        self.selector.register(self.besock, selectors.EVENT_READ, self.accept_worker)
        logger.debug("> register worker listen socket {0}".format(id(self.besock)))

        self.hb_init()

    def hb_init(self):
        self.hbsock = utils.create_client_socket(
            config.Config.asm_config_listen_ipv4,
            config.Config.asm_config_listen_port
        )
        if self.hbsock:
            self.selector.register(self.hbsock, selectors.EVENT_READ, self.hb_close)
            logger.debug("> register heartbeat socket {0}".format(self.hbsock))

    def hb_close(self, sock, event=None):
        # 心跳服务不会发送消息，因此，如果是这个 sock 可读了，那么就是
        # 对端关闭了连接
        self.selector.unregister(sock)
        sock.close()
        self.hbsock = None
        logger.debug("> heartbeat service disconnect, unregister and closed")

    # 目前使用有超时时间（3s）的建立连接 socket.connect()，如果对端出
    # 现异常，那么就会影响到处理客户端的请求（在调用 socket.connect()
    # 时，阻塞在里面的时间，不能处理客户端请求）。这里假定不会频繁地处
    # 理网络异常，同时也保持了简单性。
    #
    # 如果网络状况不好，那么就需要将建立连接的情况改为非阻塞式的，
    # socket.connect() 返回后，将之加入到 selectors.select() 里面对
    # EVENT_WRITE 事件进行监听。在事件被触发时，就表明连接已经建立成功。
    def send_heartbeat(self):
        if self.hbsock is None:
            logger.debug("< try connect to heartbeat service {0}:{1}".format(
                config.Config.asm_config_listen_ipv4,
                config.Config.asm_config_listen_port
            ))
            self.hb_init()
        else:
            body = json.dumps({
                "region_id": config.Config.region_id,
                "connect_ip": config.Config.announce_listen_ipv4,
                "connect_port": config.Config.announce_listen_port
            })
            totallen = 8 + len(body)
            hbmsg = (totallen, 0x00080001) # (totallen, command)
            outmsg = struct.pack('!II', *hbmsg)
            try:
                self.hbsock.sendall(outmsg+body.encode())
                # logger.debug("> send hearbeat to {} success".format(
                #     self.hbsock
                # ))
            except BrokenPipeError as e:
                logger.debug("socket.sendall failed: {0}".format(e))
                self.hb_close(self.hbsock)

    def run_event_loop(self):
        logger.info("select_timeout: {0}, heartbeat_interval: {1}".format(
            config.Config.select_timeout,
            config.Config.heartbeat_interval
        ))

        now = time.time()
        expire = now + config.Config.heartbeat_interval

        # 目前不考虑 NTP 的时间跳变
        while True:
            ready_list = self.selector.select(config.Config.select_timeout)

            # 如果有客户端消息，首先处理客户端消息
            for key, event in ready_list:
                callback = key.data
                callback(key.fileobj, event)

            now = time.time()
            if now > expire:
                self.send_heartbeat()
                now = time.time()
                expire = now + config.Config.heartbeat_interval