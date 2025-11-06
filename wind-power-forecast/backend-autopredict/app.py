"""自动预测服务入口。"""

from app_factory import create_app, socketio


app = create_app()


if __name__ == "__main__":  # pragma: no cover
    socketio.run(app, host="0.0.0.0", port=5001, debug=True)
