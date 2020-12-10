
from app.views import app


def run():
    app.run(debug=True, host='0.0.0.0', port=9090, threaded=False)


if __name__ == "__main__":
    run()
