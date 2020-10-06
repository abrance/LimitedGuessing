# !/usr/bin/env python
# coding: utf-8

import logging
import time
import os


def get_log(log_model_name, style='console'):
    """
    :param log_model_name: 要打印日志的模块名
    :param style: 日志打印方式，console：打印到控制台；file：打印到文件中
    :return:
    """
    # 创建一个logger
    _logger = logging.getLogger(log_model_name)
    _logger.setLevel(logging.INFO)

    # 设置日志存放路径，日志文件名
    # 获取本地实际，转换为设置的格式
    rq = time.strftime('%Y_%m_%d', time.localtime(time.time()))
    # 设置所有日志和错误日志的存放路径
    all_log_path = '/pytest_demo/log/All_Logs/'
    error_log_path = '/pytest_demo/log/Error_Logs/'

    # 判断要保存的日志文件夹是否存在，不存在就创建
    if not os.path.exists(all_log_path):
        os.mkdir(all_log_path)
    if not os.path.exists(error_log_path):
        os.mkdir(error_log_path)

    # 设置日志文件名
    all_log_name = all_log_path + rq + '.log'
    error_log_name = error_log_path + rq + '.log'
    print(all_log_name)

    if style == 'console':
        # 创建一个handler输出到控制台
        # 创建一个handler写入所有日志
        all_log = logging.StreamHandler()
        all_log.setLevel(logging.INFO)

        # 创建一个handler写入错误日志
        error_log = logging.StreamHandler(error_log_name)
        error_log.setLevel(logging.ERROR)

        # 定义日志输出格式
        # 以时间-日志名称-日志级别-日志内容的形式展示
        all_log_formatter = logging.Formatter('%(asctime)s-%(name)s-%(levelname)s-%(message)s')

        # 以时间-日志名称-日志级别-文件名-函数行数-错误内容
        error_log_formatter = logging.Formatter('%(asctime)s-%(name)s-%(levelname)s-%(module)s-%(message)s')

        # 将定义好的输出形式添加到handler
        all_log.setFormatter(all_log_formatter)
        error_log.setFormatter(error_log_formatter)

        # 给logger添加handler
        _logger.addHandler(all_log)
        _logger.addHandler(error_log)
        return _logger
    else:
        # 日志写入到文件
        # 创建一个handler写入所有日志
        all_log = logging.FileHandler(all_log_name)
        all_log.setLevel(logging.INFO)

        # 创建一个handler写入错误日志
        error_log = logging.FileHandler(error_log_name)
        error_log.setLevel(logging.ERROR)

        # 定义日志输出格式
        # 以时间-日志名称-日志级别-日志内容的形式展示
        all_log_formatter = logging.Formatter('%(asctime)s-%(name)s-%(levelname)s-%(message)s')

        # 以时间-日志名称-日志级别-文件名-函数行数-错误内容
        error_log_formatter = logging.Formatter('%(asctime)s-%(name)s-%(levelname)s-%(module)s-%(message)s')

        # 将定义好的输出形式添加到handler
        all_log.setFormatter(all_log_formatter)
        error_log.setFormatter(error_log_formatter)

        # 给logger添加handler
        _logger.addHandler(all_log)
        _logger.addHandler(error_log)
        return _logger


logger = get_log(log_model_name='Game', style='console')
