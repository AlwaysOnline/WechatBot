# -*- coding:utf-8 -*-
"""
author: chuanwu.sun
created: 2017-03-14 13:42
e-mail: chuanwusun at gmail.com
"""
import io
import json
import requests
import random
import time
import re
import xml.dom.minidom
import urllib

import qrcode
import pdir

now = lambda : int(time.time())


WECHAT_LOGIN_URL = 'https://login.weixin.qq.com/jslogin'
WECHAT_QR_CODE_STRING = 'https://login.weixin.qq.com/l/{}'
UPLOAD_IMG = 'https://sm.ms/api/upload'

headers = {
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'accept-encoding': 'gzip, deflate, br',
    'accept-language': 'zh-CN,zh;q=0.8,en-US;q=0.6,en;q=0.4',
    'cache-control': 'max-age=0',
    'host': 'login.wx.qq.com',
    'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/53.0.2785.143 Safari/537.36',
}


class WechatBot(object):

    def __init__(self):

        self.session = requests.Session()

        self.uuid = None
        self.base_uri = None
        self.base_host = None

        self.skey = None
        self.sid = None
        self.uin = None
        self.pass_ticket = None
        self.device_id = None

        self.base_request = None

        self.sync_key = None
        self.sync_key_str = None

        self.params = {}

    def get_uuid(self):
        params = {
            'appid': 'wx782c26e4c19acffb',
            'fun': 'new',
            'lang': 'zh_CN',
            '_': int(time.time()) * 1000 + random.randint(1, 999),
        }
        r = self.session.get(WECHAT_LOGIN_URL, params=params)
        r.encoding = 'utf-8'
        data = r.text
        regx = r'window.QRLogin.code = (\d+); window.QRLogin.uuid = "(\S+?)"'
        pm = re.search(regx, data)
        if pm:
            code = pm.group(1)
            self.uuid = pm.group(2)
            return code == '200'
        raise

    def get_qr_code(self):
        print self.uuid
        string = 'https://login.weixin.qq.com/l/' + self.uuid
        img = qrcode.make(string)
        img_in_memory = io.BytesIO()
        img.save(img_in_memory, 'png')
        img_in_memory.seek(0)
        files = {'smfile': img_in_memory}
        resp = requests.post(UPLOAD_IMG, files=files)
        qr_code_url = json.loads(resp.content)['data']['url']
        print qr_code_url
        return qr_code_url

    def login(self):

        redirect_url = None
        LOGIN_TEMPLATE = 'https://login.weixin.qq.com/cgi-bin/mmwebwx-bin/login?tip=%s&uuid=%s&_=%s'
        tip = 1

        while not redirect_url:
            url = LOGIN_TEMPLATE % (tip, self.uuid, now())
            resp = self.session.get(url, headers=headers)

            param = re.search(r'window.code=(\d+);', resp.text)
            code = param.group(1)

            if code == '201':
                tip = 0
            elif code == '200':
                print 'get_redirect_url'
                redirect_urls = re.search(r'\"(?P<redirect_url>.*)\"', resp.content)
                if redirect_urls:
                    redirect_url = redirect_urls.group('redirect_url') + '&fun=new'
                    self.base_uri = redirect_url[:redirect_url.rfind('/')]
                    temp_host = self.base_uri[8:]
                    self.base_host = temp_host[:temp_host.find("/")]
            else:
                tip = 1

        resp = self.session.get(redirect_url)

        doc = xml.dom.minidom.parseString(resp.text.encode('utf-8'))
        root = doc.documentElement

        for node in root.childNodes:
            if node.nodeName == 'skey':
                self.skey = node.childNodes[0].data
            elif node.nodeName == 'wxsid':
                self.sid = node.childNodes[0].data
            elif node.nodeName == 'wxuin':
                self.uin = node.childNodes[0].data
            elif node.nodeName == 'pass_ticket':
                self.pass_ticket = node.childNodes[0].data
        self.deviceid = 'e' + repr(random.random())[2:17]
        if all([self.skey, self.sid, self.uin, self.pass_ticket]):
            return True
        raise

    def init(self):

        url = self.base_uri + '/webwxinit?r=%i&lang=en_US&pass_ticket=%s' % (now(), self.pass_ticket)
 
        self.base_request = {
            'Uin': self.uin,
            'Sid': self.sid,
            'Skey': self.skey,
            'DeviceID': self.device_id,
        }
 
        params = {
            'BaseRequest': self.base_request
        }
        r = self.session.post(url, data=json.dumps(params))
        dic = json.loads(r.text.encode('utf-8'))

        self.sync_key = dic['SyncKey']
        self.sync_key_str = '|'.join(str(data['Key']) + '_' + str(data['Val']) for data in self.sync_key['List'])
        if dic['BaseResponse']['Ret'] != 0:
            raise

    def sync_check(self):
        """
        sync check.
        """

        params = {
            'r': now(),
            'skey': self.skey,
            'sid': self.sid,
            'uin': self.uin,
            'deviceid': self.deviceid,
            'synckey': self.sync_key_str,
            '_': now()
        }

        url = 'https://' + self.sync_host + '/cgi-bin/mmwebwx-bin/synccheck?' + urllib.urlencode(params)
        print url
        for i in range(10):
            try:
                r = self.session.get(url, timeout=5)
                r.encoding = 'utf-8'
                data = r.text
                pm = re.search(r'window.synccheck=\{retcode:"(\d+)",selector:"(\d+)"\}', data)
                retcode = pm.group(1)
                selector = pm.group(2)
                print 'sync_check: ', retcode, selector
                return [retcode, selector]
            except requests.exceptions.ReadTimeout:
                # FIXME
                print 'timeout'
            except:
                raise

    def sync_host_check(self):
        for host1 in ['webpush.', 'webpush2.']:
            self.sync_host = host1 + self.base_host
            try:
                retcode, selector = self.sync_check()
                print retcode, selector
                if retcode == '0':
                    print 'choose host: ', self.sync_host
                    return True
            except Exception as e:
                print e
        raise

    def sync(self):
        url = self.base_uri + '/webwxsync?sid=%s&skey=%s&lang=en_US&pass_ticket=%s' % (self.sid, self.skey, self.pass_ticket)
        params = {
            'BaseRequest': self.base_request,
            'SyncKey': self.sync_key,
            'rr': ~int(time.time())
        }
        try:
            r = self.session.post(url, data=json.dumps(params), timeout=60)
            r.encoding = 'utf-8'
            dic = json.loads(r.text)
            if dic['BaseResponse']['Ret'] == 0:
                self.sync_key = dic['SyncKey']
                self.sync_key_str = '|'.join(str(data['Key']) + '_' + str(data['Val']) for data in self.sync_key['List'])
                print 'update sync_key', self.sync_key_str
            return dic
        except Exception:
            raise

    def proc_msg(self):
        print 'sync_host_check'
        self.sync_host_check()
        print 'sync_host_check passed'

        while True:
            check_time = now()
            [retcode, selector] = self.sync_check()
            print retcode, selector
            self.sync()
            check_time = now() - check_time
            if check_time < 0.8:
                time.sleep(0.8 - check_time)

    def run(self):
        bot.get_uuid()
        bot.get_qr_code()
        bot.login()
        bot.init()
        bot.proc_msg()


if __name__ == "__main__":
    bot = WechatBot()
    bot.run()
