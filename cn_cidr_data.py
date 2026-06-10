#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# CN CIDR blocks from APNIC (auto-generated)
# Source: https://github.com/gaoyifan/china-operator-ip
# v28.99 Phase B: 改为从 JSON 懒加载（由 gen_cn_cidr.py 生成 config/cn_cidr_data.json）
#                 4242 个 IPNetwork 对象按需构建，不再嵌入源码

import ipaddress
import json
import pathlib

_CIDR_JSON = pathlib.Path(__file__).parent / "config" / "cn_cidr_data.json"


def _load():
    with open(_CIDR_JSON, 'r', encoding='utf-8') as f:
        raw = json.load(f)
    return [ipaddress.ip_network(s) for s in raw]


# 按需加载，首次访问时构建
_CACHED = None


def _get():
    global _CACHED
    if _CACHED is None:
        _CACHED = _load()
    return _CACHED


# 支持 len()
def __len__():
    return len(_get())


# 支持迭代
def __iter__():
    return iter(_get())


# 支持索引
def __getitem__(key):
    return _get()[key]


# 支持成员测试
def __contains__(item):
    return item in _get()


# 模块级变量 = 全量列表（向后兼容）
CN_IP_RANGES = _get()
