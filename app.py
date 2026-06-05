from flask import Flask, render_template, request, send_file, redirect, url_for
import os

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("panel.html")

@app.route("/cotizador")
def cotizador():
    return render_template("cotizador.html")

@app.route("/laser")
def laser():
    return render_template("laser.html")

@app.route("/ordenes")
def ordenes():
    return render_template("ordenes.html")

@app.route("/remision")
def remision():
    return render_template("remision.html")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
