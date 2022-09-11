"""Implement game logic."""

__all__ = ['Error', 'Event', 'EventName', 'Card', 'Controller', 'discard_fort',
           'get_game_state', 'get_spy_hand', 'join_game', 'pass_priority',
           'play_card', 'start_game']

from enum import Enum, auto
from functools import total_ordering
from itertools import cycle, dropwhile
from logging import getLogger
from random import choice, shuffle
from threading import Condition, Lock, Thread
from typing import Any, Mapping, NamedTuple, Sequence, TypeAlias, TypedDict
from queue import SimpleQueue

logger = getLogger(__name__)


class Error(Exception):
    """Raised when an action is invalid."""


@total_ordering
class Role(Enum):
    """A player role."""
    THE_CROWN = auto()
    DEMON_LORD = auto()
    USURPER = auto()
    KNIGHT = auto()
    CULTIST = auto()

    def __lt__(self, other: 'Role') -> bool:
        return self.value < other.value


class Card(Enum):
    """A playing card."""
    ATTACK = auto()
    DESTROY = auto()
    CAPTURE = auto()
    BACKSTAB = auto()
    HEIST = auto()
    SABOTAGE = auto()
    SPY = auto()
    DEFEND = auto()
    GOODY_BAG = auto()
    GOODY_BAG_PLUS = auto()
    BARRACKS = auto()
    FARM = auto()
    SPELL_TOWER = auto()
    FORT = auto()
    BARRIER = auto()
    BLACK_HOLE = auto()
    BLOOD_MAGIC = auto()
    NULLIFY = auto()
    ORACLE = auto()

    @property
    def is_response(self) -> bool:
        """If this card can only be played in response."""
        return self in {Card.DEFEND, Card.NULLIFY}

    @property
    def is_offensive(self) -> bool:
        """If this card is offensive."""
        return self in {Card.ATTACK, Card.DESTROY, Card.CAPTURE, Card.BACKSTAB,
                        Card.HEIST, Card.SABOTAGE, Card.SPY}

    @property
    def is_building(self) -> bool:
        """If this card is a building."""
        return self in {Card.BARRACKS, Card.FARM, Card.SPELL_TOWER, Card.FORT}

    @property
    def is_spell(self) -> bool:
        """If this card is a spell."""
        return self in {Card.BARRIER, Card.BLACK_HOLE, Card.BLOOD_MAGIC,
                        Card.NULLIFY}

    @property
    def targets_another_player(self) -> bool:
        """If this card's effect targets another player."""
        return self in {Card.CAPTURE, Card.HEIST, Card.SPY, Card.BLOOD_MAGIC}

    @property
    def targets_a_building(self) -> bool:
        """If this card's effect targets a building."""
        return self in {Card.DESTROY, Card.CAPTURE}

    @property
    def targets_a_player(self) -> bool:
        """If this card's effect targets a player."""
        return self in {Card.ATTACK, Card.DESTROY, Card.CAPTURE, Card.BACKSTAB,
                        Card.HEIST, Card.SABOTAGE, Card.SPY, Card.BLOOD_MAGIC}


def create_deck() -> list[Card]:
    """Create a deck in printable-deck order."""
    return ([Card.ATTACK] * 15
            + [Card.DESTROY] * 4
            + [Card.CAPTURE] * 3
            + [Card.BACKSTAB] * 2
            + [Card.HEIST, Card.SABOTAGE, Card.SPY]
            + [Card.DEFEND] * 9
            + [Card.GOODY_BAG] * 2
            + [Card.GOODY_BAG_PLUS]
            + [Card.BARRACKS] * 4
            + [Card.FARM] * 3
            + [Card.SPELL_TOWER] * 3
            + [Card.FORT] * 2
            + [Card.BARRIER, Card.BLACK_HOLE, Card.BLOOD_MAGIC, Card.NULLIFY]
            + [Card.ORACLE])


def shuffle_deck(deck: list[Card]) -> None:
    """Shuffle a deck."""
    shuffle(deck)
    # Ensure that the Oracle card is at the bottom.
    try:
        deck.remove(Card.ORACLE)
    except ValueError:
        # The Oracle card has been played already.
        return
    deck.insert(0, Card.ORACLE)


class Player:
    """A player state."""
    role: Role | None
    health: int
    hand: list[Card]
    buildings: list[Card]
    has_barrier: bool

    def __init__(self) -> None:
        self.role = None
        self.health = 5
        self.hand = []
        self.buildings = []
        self.has_barrier = False

    @property
    def is_alive(self) -> bool:
        """Is the player alive."""
        return self.health > 0

    @property
    def is_dead(self) -> bool:
        """Is the player dead."""
        return not self.is_alive

    @property
    def hand_limit(self) -> int:
        """The maximum number of cards in the player's hand."""
        return 5 + self.buildings.count(Card.FARM)

    @property
    def attack_damage(self) -> int:
        """The damage the player would deal if they played an Attack."""
        return 1 + self.buildings.count(Card.SPELL_TOWER)

    @property
    def attack_limit(self) -> int:
        """The number of times a player can play an Attack in one
        turn."""
        return 1 + self.buildings.count(Card.BARRACKS)

    def get_role(self) -> Role:
        """The role of the player.

        Raises an error if the player has not been assigned a role."""
        if self.role is None:
            raise Error('Player has not been assigned a role.')
        return self.role

    def draw(self, deck: list[Card], discard_pile: list[Card]) -> None:
        """Draw a card from deck.

        If deck is empty, discard_pile is shuffled in."""
        try:
            self.hand.append(deck.pop())
        except IndexError:
            # Shuffle the discard pile into the deck.
            deck.extend(discard_pile)
            discard_pile.clear()
            shuffle_deck(deck)
            # Because of hand limits, I don't think it's possible for there
            # to be no cards in either the deck or the discard pile.
            self.hand.append(deck.pop())

    def draw_to_hand_limit(self, deck: list[Card],
                           discard_pile: list[Card]) -> None:
        """Draw from deck until the hand limit is reached."""
        while len(self.hand) < self.hand_limit:
            self.draw(deck, discard_pile)


class Game:
    """A game state."""
    players: list[Player]
    deck: list[Card]
    discard_pile: list[Card]
    has_oracle_been_played: bool

    def __init__(self) -> None:
        self.players = []
        self.deck = create_deck()
        self.discard_pile = []
        self.has_oracle_been_played = False

        shuffle_deck(self.deck)

    @property
    def is_full(self) -> bool:
        """If no more players can join the game."""
        return len(self.players) == 5

    @property
    def is_spell_tower_present(self) -> bool:
        """If at least one player has a Spell Tower building."""
        return any(Card.SPELL_TOWER in player.buildings for player in self.players)

    def assign_roles(self) -> None:
        """Randomly assign roles to each player."""
        roles = list(Role)[:len(self.players)]
        shuffle(roles)
        for player, role in zip(self.players, roles):
            player.role = role


class Action(NamedTuple):
    """The playing of a card, that is, with its targets."""
    auth_player: Player
    card: Card
    target_player: Player | None = None
    target_building: Card | None = None
    is_fort_discard: bool = False


class CurrentTurn:
    """Details about the current turn."""
    player: Player
    pass_count: int
    players_count: int
    attack_count: int
    stack: list[Action]
    spy_hand: list[Card]

    def __init__(self, player: Player, players_count: int):
        self.player = player
        self.pass_count = 0
        self.players_count = players_count
        self.attack_count = 0
        self.stack = []

    @property
    def is_passed(self) -> bool:
        """If the turn should pass.

        Either the player whose turn it is does not wish to play a card,
        or all players have finished playing responses."""
        return self.pass_count == self.players_count

    @is_passed.setter
    def is_passed(self, value: bool) -> None:
        assert value is True
        self.pass_count = self.players_count


class EventName(Enum):
    """The name of an event."""
    DRAW = auto()
    STATE_UPDATE = auto()
    WIN = auto()


class EventData(TypedDict, total=False):
    """The payload of an event."""
    card: Card
    winner_ids: list[int]


class Event(TypedDict):
    """A game event."""
    name: EventName
    data: EventData


Listener: TypeAlias = SimpleQueue[Event]


class Controller:
    """Controls a game."""
    game: Game
    _current_turn: CurrentTurn | None
    listeners: list[Listener]
    cv: Condition

    def __init__(self) -> None:
        self.game = Game()
        self._current_turn = None
        self.listeners = []
        self.cv = Condition(Lock())

    def get_player(self, player_id: int) -> Player:
        """Get a player from their id."""
        try:
            return self.game.players[player_id]
        except IndexError as error:
            raise Error(f'Invalid player_id {player_id}.') from error

    @property
    def current_turn(self) -> CurrentTurn | None:
        """The current turn."""
        return self._current_turn

    @current_turn.setter
    def current_turn(self, value: CurrentTurn) -> None:
        self._current_turn = value

    def get_current_turn(self) -> CurrentTurn:
        """Get the current turn.

        Raises an error if the game has not started."""
        if self._current_turn is None:
            raise Error('Game has not started.')
        return self._current_turn

    def register_listener(self) -> Listener:
        """Register a new event listener."""
        listener: Listener = SimpleQueue()
        self.listeners.append(listener)
        return listener

    def broadcast(self, name: EventName, data: EventData | None = None) -> None:
        """Send an event to all event listeners."""
        if data is None:
            data = {}
        event: Event = {'name': name, 'data': data}
        logger.debug('Broadcasting event: %s', event)
        for listener in self.listeners:
            listener.put(event)


def get_game_state(controller: Controller, auth_player_id: int) -> Mapping[str, Any]:
    """Return the game state.

    The returned value is serialisable with json.dumps."""
    auth_player = controller.get_player(auth_player_id)

    def as_dict(player: Player) -> Mapping[str, Any]:
        result = {'health': player.health,
                  'hand_count': len(player.hand),
                  'buildings': [building.name for building in player.buildings],
                  'has_barrier': player.has_barrier}
        if ((auth_player is player
                or controller.game.has_oracle_been_played
                or player.role is Role.THE_CROWN)
                and player.role is not None):
            result['role'] = player.role.name
        if auth_player is player:
            result['hand'] = [card.name for card in player.hand]
        return result
    with controller.cv:
        game = controller.game
        players = list(map(as_dict, game.players))
        result: dict[str, Any] = {'players': players}

        current_turn = controller.current_turn
        if current_turn is not None:
            stack = [action.card.name for action in current_turn.stack]
            result['current_turn'] = {
                'stack': stack,
                'player_id': game.players.index(current_turn.player)
                }
        return result


def join_game(controller: Controller) -> int:
    """Add a new player to the game.

    Returns the id of the new player."""
    with controller.cv:
        game = controller.game
        if game.is_full:
            raise Error('Game is full.')
        game.players.append(Player())
        controller.broadcast(EventName.STATE_UPDATE)
        return len(game.players) - 1


def resolve_stack(controller: Controller) -> None:
    """Resolve the effects of the actions on the stack."""
    game = controller.game
    current_turn = controller.get_current_turn()
    stack = current_turn.stack
    while stack:
        auth_player, card, target_player, target_building, is_fort_discard = \
            stack.pop()
        if card is Card.ATTACK:
            assert target_player is not None
            target_player.health -= auth_player.attack_damage
            current_turn.attack_count += 1
        elif card is Card.DESTROY:
            assert target_player is not None
            target_player.buildings = [
                building for building in target_player.buildings
                if building is not target_building
            ]
        elif card is Card.CAPTURE:  # Sakura!
            assert target_player is not None
            assert target_building is not None
            target_player.buildings.remove(target_building)
            auth_player.buildings.append(target_building)
        elif card is Card.BACKSTAB:
            assert target_player is not None
            target_player.health -= 1
        elif card is Card.HEIST:
            assert target_player is not None
            auth_player.hand, target_player.hand = \
                target_player.hand, auth_player.hand
        elif card is Card.SABOTAGE:
            assert target_player is not None
            try:
                for _ in range(2):
                    target_player.hand.remove(choice(target_player.hand))
            except ValueError:
                # The player does not have enough cards in hand.
                pass
        elif card is Card.SPY:
            assert target_player is not None
            current_turn.spy_hand = target_player.hand.copy()
        elif card.is_response or is_fort_discard:
            # All responses counter the next card effect.
            stack.pop()
        elif card is Card.GOODY_BAG:
            for _ in range(2):
                auth_player.draw(game.deck, game.discard_pile)
        elif card is Card.GOODY_BAG_PLUS:
            for _ in range(3):
                auth_player.draw(game.deck, game.discard_pile)
        elif card.is_building:
            auth_player.buildings.append(card)
        elif card is Card.BARRIER:
            auth_player.has_barrier = True
        elif card is Card.BLACK_HOLE:
            for player in game.players:
                player.buildings.clear()
        elif card is Card.BLOOD_MAGIC:
            assert target_player is not None
            auth_player.health, target_player.health = \
                target_player.health, auth_player.health
        elif card is Card.ORACLE:
            game.has_oracle_been_played = True

        if not card.is_building:
            game.discard_pile.append(card)

        controller.broadcast(EventName.STATE_UPDATE)


def detect_win(game: Game) -> list[Player]:
    """Detect if players have won the game.

    Usually, only one player wins. However, the Knight wins if they are
    still alive and The Crown wins. It is possible for there to only be
    one living player, the Knight, but no winner."""
    # Not every role exists, so our alive and dead predicates accept
    # None as an argument.
    def find_player(role: Role) -> Player | None:
        """Find player by their role."""
        iterator = (player for player in game.players
                    if player.get_role() is role)
        return next(iterator, None)

    def is_alive(player: Player | None) -> bool:
        return player is not None and player.is_alive

    def is_dead(player: Player | None) -> bool:
        return player is None or player.is_dead
    the_crown, demon_lord, usurper, knight, cultist = \
        list(map(find_player, Role))
    if (is_alive(the_crown) and is_dead(demon_lord)
            and is_dead(usurper) and is_dead(cultist)):
        assert the_crown is not None
        if is_alive(knight):
            assert knight is not None
            return [the_crown, knight]
        return [the_crown]
    if (is_alive(demon_lord) and is_dead(the_crown) and is_dead(usurper)
            and is_dead(knight) and is_dead(cultist)):
        assert demon_lord is not None
        return [demon_lord]
    if is_alive(usurper) and is_dead(the_crown):
        assert usurper is not None
        return [usurper]
    if is_alive(cultist) and is_dead(the_crown) and is_dead(knight):
        assert cultist is not None
        return [cultist]
    return []


def detect_draw(game: Game) -> bool:
    """Detect if the game has ended in a draw.

    This happens if only the Knight is alive."""
    return len([player for player in game.players if player.is_alive]) == 1


def cycle_turns(controller: Controller) -> None:
    """Cycle through player turns, waiting for actions."""
    with controller.cv:
        game = controller.game
        # Start from the player that is The Crown. I have agonised over
        # the arrangement of these six lines.
        iterator = dropwhile(lambda player: player.role is not Role.THE_CROWN,
                             cycle(game.players))
        for player in iterator:
            # Skip dead players.
            if player.is_dead:
                continue
            current_turn = CurrentTurn(player, len(game.players))
            controller.current_turn = current_turn

            player_id = game.players.index(player)
            data: EventData = {'player_id': player_id}
            controller.broadcast(EventName.STATE_UPDATE)
            logger.info('Player %s\'s turn', player_id)

            player.has_barrier = False
            is_ended = False
            while not is_ended:
                current_turn.pass_count = 0
                while not current_turn.is_passed:
                    if not controller.cv.wait(timeout=20):
                        current_turn.is_passed = True
                    # If players passed and no cards were played, then
                    # the turn is ended.
                    if not current_turn.stack:
                        is_ended = True
                resolve_stack(controller)

                winners = detect_win(game)
                if winners:
                    winner_ids = list(map(game.players.index, winners))
                    data = {'winner_ids': winner_ids}
                    controller.broadcast(EventName.WIN, data)
                    controller._current_turn = None
                    return
                if detect_draw(game):
                    controller.broadcast(EventName.DRAW)
                    controller._current_turn = None
                    return
            player.draw_to_hand_limit(game.deck, game.discard_pile)
            controller.broadcast(EventName.STATE_UPDATE)


def start_game(controller: Controller) -> None:
    """Start the game."""
    with controller.cv:
        game = controller.game
        if controller.current_turn is not None:
            raise Error('Game has already started.')
        if len(game.players) < 2:
            raise Error('Not enough players to start.')
        game.assign_roles()
        for player in game.players:
            player.draw_to_hand_limit(game.deck, game.discard_pile)
        controller.broadcast(EventName.STATE_UPDATE)
        Thread(target=cycle_turns, args=(controller,), daemon=True).start()
    logger.info('Game has started.')


def pass_priority(controller: Controller, auth_player_id: int) -> None:
    """Pass priority."""
    with controller.cv:
        auth_player = controller.get_player(auth_player_id)
        current_turn = controller.get_current_turn()
        if not current_turn.stack:
            if auth_player is current_turn.player:
                # If the stack is empty, then the player whose turn it is can end
                # the turn.
                current_turn.is_passed = True
            else:
                raise Error('It is not your turn.')
        else:
            current_turn.pass_count += 1
        logger.debug(current_turn.pass_count)
        controller.cv.notify()


def play_card(controller: Controller, auth_player_id: int, card: Card,
              target_player_id: int | None = None,
              target_building: Card | None = None) -> None:
    """Play a card from hand."""
    with controller.cv:
        auth_player = controller.get_player(auth_player_id)
        if target_player_id is not None:
            target_player = controller.get_player(target_player_id)
        else:
            target_player = None
        current_turn = controller.get_current_turn()
        stack = current_turn.stack
        game = controller.game
        # Check that the action is valid.
        if card not in auth_player.hand:
            raise Error('You do not have that card in your hand.')
        if not stack:
            if auth_player is not current_turn.player:
                raise Error('It is not your turn.')
            if card.is_response:
                raise Error('That card can only be played as a response.')
            if card.targets_a_player:
                if target_player is None:
                    raise Error('No target player.')
                if target_player.has_barrier:
                    raise Error('Target player played Barrier.')
            if card.targets_another_player and target_player is auth_player:
                raise Error('You cannot target yourself.')
            if card.targets_a_building:
                assert target_player is not None
                if target_building is None:
                    raise Error('No target building.')
                if target_building not in target_player.buildings:
                    raise Error(
                        'The target player does not have that building.')
            if (card is Card.ATTACK
                    and current_turn.attack_count >= auth_player.attack_limit):
                raise Error('You have reached your attack limit.')
            if card.is_spell and not game.is_spell_tower_present:
                raise Error('No spell tower present.')
        else:
            # The stack is not empty, so only responses are allowed.
            if not card.is_response:
                raise Error('That card cannot be played as a response.')
            if card is Card.DEFEND and not stack[-1].card.is_offensive:
                raise Error('Card is not offensive.')
        # Put the action on the stack.
        auth_player.hand.remove(card)
        action = Action(auth_player, card, target_player, target_building)
        current_turn.stack.append(action)
        controller.broadcast(EventName.STATE_UPDATE)
        controller.cv.notify()


def discard_fort(controller: Controller, auth_player_id: int) -> None:
    """Discard a played Fort building."""
    with controller.cv:
        auth_player = controller.get_player(auth_player_id)
        stack = controller.get_current_turn().stack
        if Card.FORT not in auth_player.buildings:
            raise Error('You do not have a Fort to discard.')
        if not stack:
            raise Error('A Fort can only be discarded as a response.')
        if stack[-1].card is not Card.ATTACK:
            raise Error('The last card was not an Attack.')

        auth_player.buildings.remove(Card.FORT)
        controller.game.discard_pile.append(Card.FORT)

        action = Action(auth_player, Card.FORT, is_fort_discard=True)
        stack.append(action)
        controller.broadcast(EventName.STATE_UPDATE)
        controller.cv.notify()


def get_spy_hand(controller: Controller, auth_player_id: int) -> Sequence[str]:
    """Get the hand revealed by a Spy card this turn.

    The returned value is serialisable with json.dumps."""
    with controller.cv:
        auth_player = controller.get_player(auth_player_id)
        current_turn = controller.get_current_turn()
        if auth_player is not current_turn.player:
            raise Error('You did not play the Spy card.')
        return [card.name for card in current_turn.spy_hand]
