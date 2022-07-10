from flask import Flask, redirect, render_template, url_for
from flask_sock import Sock
from json import dumps, loads

from oracle.lobby import Lobby
from oracle.bus import Action

# Create our Flask application.
app = Flask(__name__)
# Extend Flask with WebSocket support.
sock = Sock(app)

# Eventually, we may support multiple games running at the same time. For now,
# there is only one.
lobby = Lobby()

@app.route('/game')
def get_game():
    # Respond with the page.
    return render_template('game.html')

@sock.route('/game')
def handle_connection(ws):
    # Once the game starts, we send our actions through a queue.
    sender, receiver = lobby.join()

    while True:
        # Serialise events to JSON before sending them over the connection.
        json = dumps(receiver.get())
        ws.send(json)
        # Deserialise actions from JSON before sending them to the game.
        action = Action._make(loads(ws.receive()))
        sender.put(action)

@app.route('/')
def redirect_to_game():
    # Since, for now, there is only one page, redirect there.
    return redirect(url_for('get_game'))
