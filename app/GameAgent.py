# -*- coding: utf-8 -*-

import selectors
import struct
import json
import datetime

import config
import utils
import models
import argchk
import message

from log import logger


def generate_response(  # header
        dst_type, dst_id, transaction_id, sequence,
        command_rsp, ack_code_rsp,
        total, offset, count,
        # body
        payload_pack=b''
):
    total_size = struct.calcsize(config.Constant.FMT_COMMON_HEAD) \
                 + len(payload_pack)
    header_rsp_unpack = (
        total_size, config.Constant.MAJOR_VERSION, config.Constant.MINOR_VERSION,
        config.Constant.METADATA_TYPE, dst_type,
        config.Config.src_id, dst_id, transaction_id, sequence,
        command_rsp, ack_code_rsp,
        total, offset, count
    )
    header_rsp_pack = struct.pack(
        config.Constant.FMT_COMMON_HEAD, *header_rsp_unpack)
    return header_rsp_pack + payload_pack


class Worker(object):

    def __init__(self):
        # 到分发者的连接
        self.sock = None

        # 到数据库的连接，接收分发者的请求后，转发到后端数据库。这个数据库连接是
        # 阻塞式的，因此同一个客户端连接发起的更改数据的请求，为了保持简单和正确
        # 性，应该发到同一个后端工作者
        self.db = None

        # 用于监听分发者的消息
        self.selector = None

        # 保存数据库所有的迁移记录到内存中
        self.migration_cached = []

    def connect_dispatcher(self, ip, port):
        self.sock = utils.create_client_socket(ip, port)

    def connect_database(self, ident):
        self.db = models.Database()
        # if ident == 0:
        #     self.db.create_tables()
        # else:
        #     # 其他进程不用创建表
        #     pass

    def on_recv_from_dispatcher(self, sock, event):
        """从分发者接收到消息后的处理
        将数据发送到数据库是阻塞的，将数据发回到分发者也是阻塞的。据我所知，底下
        的数据库接口都是阻塞式的，所以使用数据库的第三方模块（SQLAlchemy），没有
        办法实现异步的消息收发。而将结果发送回分发者，是可以进行异步处理的，但是
        在这两个进程间，不太可能出现阻塞的情况。
        """
        packet = utils.recv_packet(sock)
        if packet:
            self.handle_command(packet)
        else:
            logger.error("recv_packet failed")

    def handle_command(self, packet):

        def send_failure():
            _head = packet[0:64]
            h = message.Header.unpack(_head)
            h.command += 1
            h.ack_code = config.Constant.ACK_FAILED
            _head = h.pack()
            self.sock.sendall(_head)

        head = packet[0:64]
        header_unpack = struct.unpack(message.HEADER_FORMAT, head)
        command = header_unpack[9]

        if command in config.command_str.keys():
            logger.info("receive command {0}".format(config.command_str[command]))
        else:
            logger.info("receive unknown command 0x{0:x}".format(command))
            send_failure()
            return None

        # 临时性的修改
        msg = packet[64:]
        try:
            body_unpack = json.loads(msg.decode("utf-8"))
        except Exception:
            send_failure()
            return None

        if command == config.Constant.CLIENT_QUERY_STUDY_LIST:
            timestamp_before = body_unpack.get("timestamp_before")
            nr_study = body_unpack.get("nr_study")
            study_state = body_unpack.get("study_state")
            study_id = body_unpack.get("study_id")
            nr_files = body_unpack.get("nr_files")
            args = header_unpack + (timestamp_before, nr_study, study_state, study_id, nr_files)
            self.handle_query_study_list(*args)
        elif command == config.Constant.CLIENT_QUERY_STUDY_LIST2:
            self.handle_query_study_list2(packet)
        elif command == config.Constant.CLIENT_UPLOAD_SUCCESS_NOTIFY:
            self.handle_upload_success_notify(packet)
        elif command == config.Constant.CLIENT_UPLOAD_FAILED_NOTIFY:
            study_id = body_unpack.get("study_id")
            args = header_unpack + (study_id,)
            self.handle_client_upload_failed_notify(*args)

        elif command == config.Constant.CLIENT_DEAD_NOTIFY:
            self.handle_query_agent_id_dead(*header_unpack)
        else:
            # already output command type, do nothing
            pass

    def send_header_response(self,
                             # header
                             dst_type, dst_id, transaction_id, sequence,
                             command_rsp, ack_code_rsp,
                             total, offset, count
                             ):
        response = generate_response(
            dst_type, dst_id, transaction_id, sequence,
            command_rsp, ack_code_rsp,
            total, offset, count
        )
        resplen = len(response)
        try:
            self.sock.sendall(response)
            logger.debug("> send header {0} bytes to dispatcher".format(
                resplen))
        except OSError as e:
            logger.error("> send header {0} bytes failed: {1}".format(
                resplen, e))

    def send_payload_response(self,
                              # header
                              dst_type, dst_id, transaction_id, sequence,
                              command_rsp, ack_code_rsp,
                              total, offset, count,
                              # payload
                              payload_pack
                              ):
        response = generate_response(
            dst_type, dst_id, transaction_id, sequence,
            command_rsp, ack_code_rsp,
            total, offset, count,
            payload_pack
        )
        resplen = len(response)
        try:
            self.sock.sendall(response)
            logger.debug("> send payload {0} bytes to dispatcher".format(
                resplen))
        except OSError as e:
            logger.error("> send payload {0} bytes failed: {1}".format(
                resplen, e))

    def handle_client_upload_failed_notify(self,
                                           # header
                                           total_size,
                                           major, minor,
                                           src_type, dst_type,
                                           src_id, dst_id,
                                           transaction_id, sequence,
                                           command, ack_code,
                                           total, offset, count,

                                           # metadata
                                           study_id
                                           ):
        def check_args():
            if not ((type(study_id) is str) or (type(study_id) is bytes)):
                logger.error("study_id {} is not str or bytes!".format(study_id))
                return False
            else:
                # 参数检查正确，继续处理
                pass
            return True

        logger.debug("agent_id: {}".format(src_id))
        logger.debug("study_id: {}".format(study_id))

        args_is_valid = check_args()
        if args_is_valid:
            logger.error("self.db.handle_client_upload_failed_notify beg")
            retcode = self.db.handle_upload_failed(study_id)
            logger.error("self.db.handle_client_upload_failed_notify end")
            if retcode:
                ack_code_rsp = config.Constant.ACK_SUCCESS
            else:
                ack_code_rsp = config.Constant.ACK_FAILED
                logger.error("self.db.handle_client_upload_failed_notify not success")
        else:
            ack_code_rsp = config.Constant.ACK_FAILED
            logger.error("args is invalid")

        self.send_header_response(
            src_type, src_id, transaction_id, sequence,
            config.Constant.CLIENT_UPLOAD_FAILED_NOTIFY_RESP, ack_code_rsp,
            total, offset, count
        )

    def handle_query_study_list(self,
                                # header
                                total_size,
                                major, minor,
                                src_type, dst_type,
                                src_id, dst_id,
                                transaction_id, sequence,
                                command, ack_code,
                                total, offset, count,

                                # metadata
                                timestamp_before, nr_study, study_state,
                                study_id, nr_files
                                ):
        def check_args():
            if not (type(timestamp_before) is int):
                logger.warning("timestamp_before {} is not int!".format(timestamp_before))
                return False
            if not (type(nr_study) is int):
                logger.warning("nr_study {} is not int!".format(nr_study))
                return False
            else:
                if nr_study < 0:
                    logger.warning("nr_study {} must be >0!".format(nr_study))
                    return False
                else:
                    pass
            if not ((type(study_id) is str) or (type(study_id) is bytes)):
                logger.warning("study_id {} is not str or bytes!".format(study_id))
                return False
            if not (type(nr_files) is int):
                logger.warning("nr_files {} is not int!".format(nr_files))
                return False
            if not (type(study_state) is int):
                logger.warning("study_state {} is not int!".format(study_state))
                return False
            else:
                if not (0 <= study_state <= 4):
                    logger.warning("study_state {} is not 0..4!".format(study_state))
                    return False
                else:
                    # 合法值，0..4
                    pass
            return True

        args_is_valid = check_args()
        if args_is_valid:
            stime = datetime.datetime.fromtimestamp(timestamp_before)
            logger.debug("agent_id: {}".format(src_id))
            logger.debug("timestamp_before: {}".format(stime.strftime("%Y-%m-%d %H:%M:%S")))
            logger.debug("study_state: {}".format(study_state))
            logger.debug("nr_study: {}".format(nr_study))
            logger.debug("study_id: {}".format(study_id))
            logger.debug("nr_files: {}".format(nr_files))
            logger.debug("self.db.query_study_list beg")
            serials_metadata = self.db.query_study_list(
                timestamp_before, src_id, nr_study, study_state,
                study_id, nr_files
            )
            if serials_metadata:
                payload_pack = json.dumps(serials_metadata).encode('utf-8')
                ack_code_rsp = config.Constant.ACK_SUCCESS
            else:
                payload_pack = b''
                ack_code_rsp = config.Constant.ACK_FAILED
                logger.debug("no serial metadata")
            logger.debug("self.db.query_study_list end")
        else:
            payload_pack = b''
            ack_code_rsp = config.Constant.ACK_FAILED
            logger.error("args is invalid")

        self.send_payload_response(
            src_type, src_id, transaction_id, sequence,
            config.Constant.CLIENT_QUERY_STUDY_LIST_RESP, ack_code_rsp,
            0, 0, 0,
            payload_pack
        )

    def send_header_failure(self, head):
        h = message.Header.unpack(head)
        h.command += 1
        h.ack_code = config.Constant.ACK_FAILED
        head = h.pack()
        self.sock.sendall(head)
        return None

    def handle_query_study_list2(self, packet):
        head = packet[0:message.HEADER_SIZE]
        h = message.Header.unpack(head)
        msg = packet[message.HEADER_SIZE:]
        try:
            metadata = json.loads(msg.decode("utf-8"))
        except Exception:
            logger.error("invalid metadata!")
            return self.send_header_failure(head)
        else:
            expect = {"agent_id", "timestamp_beg", "timestamp_end", "nr_study", "study_state"}
            args_is_valid = argchk.general_check_args(metadata, expect)
            if args_is_valid:
                agent_id = h.src_id
                tsbeg = metadata.get("timestamp_beg")
                s1 = datetime.datetime.fromtimestamp(tsbeg)
                tsend = metadata.get("timestamp_end")
                s2 = datetime.datetime.fromtimestamp(tsend)
                study_state = metadata.get("study_state")
                nr_study = metadata.get("nr_study")

                logger.debug("agent_id: {}".format(agent_id))
                logger.debug("timestamp_beg: {}".format(s1))
                logger.debug("timestamp_end: {}".format(s2))
                logger.debug("study_state: {}".format(study_state))
                logger.debug("nr_study: {}".format(nr_study))

                logger.debug("self.db.query_study_list2 beg")
                study_metadata = self.db.query_study_list2(
                    tsbeg, tsend, agent_id, nr_study, study_state
                )
                if study_metadata:
                    payload_pack = json.dumps(study_metadata).encode("utf-8")
                    ack_code_rsp = config.Constant.ACK_SUCCESS
                else:
                    logger.debug("no study metadata")
                    payload_pack = b''
                    ack_code_rsp = config.Constant.ACK_FAILED
                logger.debug("self.db.query_study_list2 end")

            else:
                logger.error("args is invalid!")
                payload_pack = b''
                ack_code_rsp = config.Constant.ACK_FAILED

            # 发送响应
            h.command = config.Constant.CLIENT_QUERY_STUDY_LIST2_RESP
            h.ack_code = ack_code_rsp
            h.total_size = message.HEADER_SIZE + len(payload_pack)
            head = h.pack()
            pack = head + payload_pack
            self.sock.sendall(pack)

    def handle_upload_success_notify(self, packet):
        head = packet[0:message.HDRLEN]
        h = message.Header.unpack(head)
        msg = packet[message.HDRLEN:]
        try:
            m = json.loads(msg.decode("utf-8"))
        except Exception:
            logger.error("invalid metadata!")
            return self.send_header_failure(head)
        else:
            # 检查参数
            expect = {"nr_upload", "upload_list"}
            args_is_valid = argchk.general_check_args(m, expect)
            if args_is_valid:
                agent_id = h.src_id
                finish_list = m.get("upload_list")

                logger.debug("agent_id: {}".format(agent_id))
                logger.debug("finish_list: {}".format(finish_list))

                logger.debug("self.db.handle_upload_success beg")
                rc = self.db.handle_upload_success(agent_id, finish_list)
                logger.debug("self.db.handle_upload_success end")
                if rc:
                    ack_code_rsp = config.Constant.ACK_SUCCESS
                else:
                    ack_code_rsp = config.Constant.ACK_FAILED
            else:
                logger.error("args is invalid!")
                ack_code_rsp = config.Constant.ACK_FAILED
                payload_pack = b''

            # 发送响应
            h.command = config.Constant.CLIENT_UPLOAD_SUCCESS_NOTIFY_RESP
            h.ack_code = ack_code_rsp
            h.total_size = message.HDRLEN
            head = h.pack()
            self.sock.sendall(head)

    def handle_query_agent_id_dead(self,
                                   # header
                                   total_size,
                                   major, minor,
                                   src_type, dst_type,
                                   src_id, dst_id,
                                   transaction_id, sequence,
                                   command, ack_code,
                                   total, offset, count,
                                   ):
        logger.debug("agent_id: {}".format(src_id))

        logger.debug("self.db.handle_query_agent_id_dead beg")
        retcode = self.db.query_agent_id_dead(src_id)
        logger.debug("self.db.handle_query_agent_id_dead end")
        if retcode:
            ack_code_rsp = config.Constant.ACK_SUCCESS
        else:
            ack_code_rsp = config.Constant.ACK_FAILED
            logger.error("self.db.handle_query_agent_id_dead not success")

        self.send_header_response(
            src_type, src_id, transaction_id, sequence,
            config.Constant.CLIENT_DEAD_NOTIFY_RESP, ack_code_rsp,
            total, offset, count
        )

    def run(self, ident):
        """接收分发者的消息，转发到数据库"""
        self.connect_dispatcher(config.Config.local_dispatcher_listen_ipv4, config.Config.local_dispatcher_listen_port)
        self.connect_database(ident)

        self.selector = selectors.DefaultSelector()
        self.selector.register(self.sock, selectors.EVENT_READ, self.on_recv_from_dispatcher)

        while True:
            try:
                ready_list = self.selector.select()
            except KeyboardInterrupt:
                logger.info("receive KeyboardInterrupt, process exit")
                import sys
                sys.exit(0)
            else:
                for key, event in ready_list:
                    callback = key.data
                    callback(key.fileobj, event)
