from app import create_app

app = create_app()

if __name__ == "__main__":
    # Local development only. Production uses gunicorn against this same
    # `app` object (see STAGE2_README.md for the exact command).
    app.run(debug=True, port=5000)
