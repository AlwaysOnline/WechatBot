# -*- coding:utf-8 -*-
"""
author: chuanwu.sun
created: 2017-03-10 19:41
e-mail: chuanwusun at gmail.com
"""
from tinker.core import r


def test_ping_case():
    assert r.call_method('ping') == 'pong'

if __name__ == '__main__':
    pass
