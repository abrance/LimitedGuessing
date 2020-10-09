
from flask import Flask

app = Flask(__name__)

@app.route("/")
def index():
    return "<h1> index </h1>"


def run():
    app.run(debug=True)


if __name__ == "__main__":
    run()
