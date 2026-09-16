from app import create_app
from config import Config
from socketio_extension import socketio


app = create_app()

socketio.init_app(
    app,
    cors_allowed_origins=Config.CORS_ORIGINS,
)


if __name__ == "__main__":
    socketio.run(app, debug=True, port=5000)