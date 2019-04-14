#!/usr/bin/env python2.7

import sys, os, requests, lxml.html, json
from HTMLParser import HTMLParser
from urllib3 import HTTPSConnectionPool


class MyException(Exception):
    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return self.msg


def get_etree(url, qry={}):
    for i in range(4):
        try:
            r = requests.get(url, qry)
            if 200 <= r.status_code < 300:
                break
            sys.stderr.write("\r\nutil.get_etree(): Status code: %s\r\nResponse text: '%s'\r\n\r\n" % (str(r.status_code), r.text))
        except IOError as e:
            sys.stderr.write("\r\nERROR: util.get_etree(): '%s'\r\n\r\n" % type(e).__name__)
        except Exception as e:
            sys.stderr.write("\r\nERROR: util.get_etree(): '%s'\r\n\r\n" % type(e).__name__)
        if i == 3:
            raise MyException("util.get_etree(): Unable to GET\r\n\turl: '%s'" % url)
    return lxml.html.fromstring(r.text)


def post_etree(url, qry={}):
    for i in range(4):
        try:
            r = requests.post(url, qry)
            if 200 <= r.status_code < 300:
                break
            sys.stderr.write("\r\nutil.post_etree(): Status code: %s\r\nResponse text: '%s'\r\n\r\n" % (str(r.status_code), r.text))
        except IOError as e:
            sys.stderr.write("\r\nERROR: util.post_etree(): '%s'\r\n\r\n" % type(e).__name__)
        except Exception as e:
            sys.stderr.write("\r\nERROR: util.post_etree(): '%s'\r\n\r\n" % type(e).__name__)
        if i == 3:
            raise MyException("util.post_etree(): Unable to POST\r\n\turl: '%s'\r\n\tquery: '%s'" % (url, str(qry)))
    return lxml.html.fromstring(r.text)


def html_unescape(txt):
    return HTMLParser().unescape(txt)


JSON_DIR = "json"
DB_DIR = "db"


def table_exists(table):
    fname = os.path.sep.join((JSON_DIR, DB_DIR, table + ".json"))
    return os.path.isfile(fname)


def list_json(dirname):
    dirname = os.path.sep.join((JSON_DIR, dirname))
    if os.path.isdir(dirname):
        return [f[:-5] for f in os.listdir(dirname) if f[-5:] == ".json"]
    else:
        return []


def loader(table, dirname=DB_DIR):
    dirname = os.path.sep.join((JSON_DIR, dirname))
    fname = os.path.sep.join((dirname, table + ".json"))
    if not os.path.isdir(dirname):
        raise MyException("util.loader(): Directory '%s' does not exist" % dirname)
    if not os.path.isfile(fname):
        raise MyException("util.loader(): File '%s/%s' does not exist" % (dirname, fname))
    f = open(fname, 'r')
    js = json.loads(f.read())
    f.close()
    return js


def dumper(table, obj, dirname=DB_DIR):
    dirname = os.path.sep.join((JSON_DIR, dirname))
    fname = os.path.sep.join((dirname, table + ".json"))
    if not os.path.isdir(dirname):
        os.makedirs(dirname)
    f = open(fname, 'w')
    f.write(json.dumps(obj))
    f.close()

