"""Gunicorn 使用的 Flask 应用入口。"""

import gevent.monkey

gevent.monkey.patch_all()

from app import app as application


app = application
