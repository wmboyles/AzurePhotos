import os

from flask import Flask, render_template, request, send_from_directory

app = Flask(__name__)


@app.route("/favicon.ico")
def favicon():
    return send_from_directory(
        os.path.join(app.root_path, "static"),
        "favicon.ico",
        mimetype="image/vnd.microsoft.icon",
    )


@app.route("/")
def index():
    print("Request for index page received")
    print(request.headers)

    name = request.headers.get("X-MS-CLIENT-PRINCIPAL-NAME", "DEV")

    return render_template("index.html", name=name)


if __name__ == "__main__":
    app.run()
