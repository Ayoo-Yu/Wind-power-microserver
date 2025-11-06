"""日志公共配置。"""

import logging
import os
from datetime import datetime, timedelta, timezone
from logging.handlers import TimedRotatingFileHandler


class BeijingTimeFormatter(logging.Formatter):
    """使用北京时间的日志格式化器。"""

    def formatTime(self, record, datefmt=None):  # type: ignore[override]
        dt_utc = datetime.fromtimestamp(record.created, tz=timezone.utc)
        dt_beijing = dt_utc.astimezone(timezone(timedelta(hours=8), name="Asia/Shanghai"))

        if datefmt:
            return dt_beijing.strftime(datefmt)

        base = dt_beijing.strftime("%Y-%m-%d %H:%M:%S")
        return f"{base},{int(record.msecs):03d}"


class SocketIOHandler(logging.Handler):
    """通过 Socket.IO 推送日志。"""

    def __init__(self, socketio):  # type: ignore[override]
        super().__init__()
        self.socketio = socketio

    def emit(self, record):  # type: ignore[override]
        log_entry = self.format(record)
        print(f"Emitting log: {log_entry}")
        self.socketio.emit("log", {"message": log_entry})


def configure_logging(app, socketio, *, log_dir: str = "logs", filename: str = "app.log") -> None:
    """为 Flask/Sokcet.IO 应用统一配置日志。"""

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)

    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    file_handler = TimedRotatingFileHandler(
        os.path.join(log_dir, filename), when="midnight", interval=1, backupCount=30, encoding="utf-8"
    )
    file_handler.setLevel(logging.INFO)

    socketio_handler = SocketIOHandler(socketio)
    socketio_handler.setLevel(logging.INFO)

    formatter = BeijingTimeFormatter("[%(asctime)s] %(levelname)s in %(module)s: %(message)s")
    for handler in (console_handler, file_handler, socketio_handler):
        handler.setFormatter(formatter)

    app.logger.handlers.clear()
    app.logger.addHandler(console_handler)
    app.logger.addHandler(file_handler)
    app.logger.addHandler(socketio_handler)
    app.logger.setLevel(logging.DEBUG)

    engineio_logger = logging.getLogger("engineio")
    engineio_logger.handlers.clear()
    engineio_logger.addHandler(console_handler)
    engineio_logger.addHandler(file_handler)
    engineio_logger.addHandler(socketio_handler)
    engineio_logger.propagate = False
    engineio_logger.setLevel(logging.DEBUG)

    app.logger.info("Wind Forecast Backend Startup with unified logging configuration")


__all__ = [
    "BeijingTimeFormatter",
    "SocketIOHandler",
    "configure_logging",
]


