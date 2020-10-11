
from flask import Flask
from app.views import get_game_info


app = Flask(__name__)

@app.route("/")
def index():
    return "<h1> index </h1>"


def run():
    app.run(debug=True)


if __name__ == "__main__":
    get_game_info()
    run()
