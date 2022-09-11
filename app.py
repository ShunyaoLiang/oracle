"""Provide a WSGI application for the game."""

import logging

from functools import wraps
from http import HTTPStatus
from json import JSONEncoder, dumps
from os import environ
from typing import Any, Callable

from flask import Flask, g, render_template, request
from flask.typing import ResponseReturnValue
from flask_sock import Sock  # type: ignore
from simple_websocket import Server  # type: ignore

from oracle import Card, Controller, EventName

import oracle

# Use the logging level specified by an environment variable, or show up to
# warnings otherwise.
logging.basicConfig(level=(environ.get('ORACLE_LOG') or 'WARNING').upper())

# Eventually, we may support multiple games running at the same time. For now,
# there is only one.
controller = Controller()

# Create our Flask application.
app = Flask(__name__)
# Extend Flask with WebSocket support.
sock = Sock(app)


def require_auth_player_id(f: Callable[..., ResponseReturnValue]) \
        -> Callable[..., ResponseReturnValue]:
    """Ensure requests have an auth-player-id header."""
    @wraps(f)
    def inner(*args: Any, **kwargs: Any) -> ResponseReturnValue:
        try:
            g.auth_player_id = int(str(request.headers['auth-player-id']))
        except KeyError:
            return 'No auth-player-id header.', HTTPStatus.UNAUTHORIZED
        except IndexError:
            return 'Invalid auth-player-id.', HTTPStatus.BAD_REQUEST
        return f(*args, **kwargs)
    return inner


@app.route('/app')
def get_app() -> ResponseReturnValue:
    """Render the application page."""
    return render_template('app.html')


@app.route('/game')
@require_auth_player_id
def get_game_state() -> ResponseReturnValue:
    """Return the game state."""
    return oracle.get_game_state(controller, g.auth_player_id)


class EventEncoder(JSONEncoder):
    """Serialise oracle.Event to JSON."""

    def default(self, o: object) -> Any:
        if isinstance(o, EventName | Card):
            return o.name
        return JSONEncoder.default(self, o)


@sock.route('/game')  # type: ignore
def handle_connection(ws: Server) -> None:
    """Handle WebSocket connections."""
    app.logger.info('New WebSocket connection.')
    bus = controller.register_listener()
    while True:
        event = bus.get()
        json = dumps(event, cls=EventEncoder)
        ws.send(json)


@app.route('/game/join', methods=['POST'])
def join_game() -> ResponseReturnValue:
    """Add a new player to the game."""
    return {'auth_player_id': oracle.join_game(controller)}, HTTPStatus.CREATED


@app.route('/game/start', methods=['POST'])
def start_game() -> ResponseReturnValue:
    """Start the game."""
    oracle.start_game(controller)
    return '', HTTPStatus.NO_CONTENT


@app.route('/game/pass', methods=['POST'])
@require_auth_player_id
def pass_priority() -> ResponseReturnValue:
    """Pass priority."""
    oracle.pass_priority(controller, g.auth_player_id)
    return '', HTTPStatus.NO_CONTENT


@app.route('/game/play', methods=['POST'])
@require_auth_player_id
def play_card() -> ResponseReturnValue:
    """Play a card from hand."""
    # request.json returns Optional because it has the option to
    # silently fail. Because we have not enabled that, we can assume
    # that it is not None.
    assert request.json is not None
    try:
        card = Card[request.json['card_name']]
    except KeyError:
        return 'Missing or invalid card_name.', HTTPStatus.BAD_REQUEST
    try:
        target_player_id = int(request.json['target_player_id'])
    except KeyError:
        target_player_id = None
    try:
        target_building_name = request.json['target_building_name']
    except KeyError:
        target_building_name = None
    if target_building_name is not None:
        try:
            target_building = Card[target_building_name]
        except KeyError:
            return 'Invalid target_building_name.', HTTPStatus.BAD_REQUEST
    else:
        target_building = None
    oracle.play_card(controller, g.auth_player_id, card,
                     target_player_id, target_building)
    return '', HTTPStatus.NO_CONTENT


@app.route('/game/discard_fort', methods=['POST'])
@require_auth_player_id
def discard_fort() -> ResponseReturnValue:
    """Discard a played Fort building."""
    oracle.discard_fort(controller, g.auth_player_id)
    return '', HTTPStatus.NO_CONTENT


@app.route('/game/spy_hand')
@require_auth_player_id
def get_spy_hand() -> ResponseReturnValue:
    """Get the hand revealed by a Spy card this turn."""
    return {'spy_hand': oracle.get_spy_hand(controller, g.auth_player_id)}


@app.errorhandler(oracle.Error)
def handle_oracle_error(error: oracle.Error) -> ResponseReturnValue:
    """Respond to an oracle.Error."""
    return str(error), HTTPStatus.BAD_REQUEST
