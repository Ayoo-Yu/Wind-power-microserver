"""自动预测服务入口。"""

from app_factory import create_app, socketio
import os


app = create_app()


if __name__ == "__main__":  # pragma: no cover
    host = os.environ.get("APP_HOST", "0.0.0.0")
    port = int(
        os.environ.get(
            "AUTOPREDICT_PORT",
            os.environ.get("APP_PORT", "5001"),
        )
    )
    debug = os.environ.get("FLASK_DEBUG", "True").lower() == "true"
    socketio.run(app, host=host, port=port, debug=debug)
