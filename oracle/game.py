from dataclasses import dataclass, field
from enum import IntEnum, auto
from random import shuffle

from .bus import Bus


class Role(IntEnum):
    THE_CROWN = auto()
    DEMON_LORD = auto()
    USURPER = auto()
    KNIGHT = auto()
    CULTIST = auto()

class Card(IntEnum):
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

    @staticmethod
    def create_deck():
        return (
            [Card.ATTACK] * 15 +
            [Card.DESTROY] * 4 +
            [Card.CAPTURE] * 3 +
            [Card.BACKSTAB] * 2 +
            [Card.HEIST, Card.SABOTAGE, Card.SPY] +
            [Card.DEFEND] * 9 +
            [Card.GOODY_BAG] * 2 +
            [Card.GOODY_BAG_PLUS] +
            [Card.BARRACKS] * 4 +
            [Card.FARM] * 3 +
            [Card.SPELL_TOWER] * 3 +
            [Card.FORT] * 2 +
            [Card.BARRIER, Card.BLACK_HOLE, Card.BLOOD_MAGIC, Card.NULLIFY] +
            [Card.ORACLE]
        )

    @staticmethod
    def shuffle_deck(deck):
        shuffle(deck)
        # Ensure that the Oracle card is at the bottom.
        try:
            deck.remove(Card.ORACLE)
            deck.append(Card.ORACLE)
        except ValueError:
            pass

@dataclass
class Player:
    id_: int
    role: Role
    bus: Bus
    hand: list[Card] = field(default_factory=list)

    hand_limit = 5

    def draw_to_limit(self, deck: list[Card]):
        while len(self.hand) < self.hand_limit:
            self.hand.append(deck.pop())

    def send_start_event(self, the_crown_id: int):
        self.bus.send({
            'op': 0,
            'id': self.id_,
            'role': self.role,
            'hand': self.hand,
            'the_crown_id': the_crown_id,
        })

class Game:
    players: list[Player]
    deck: list[Card]

    def __init__(self, buses):
        # Assign roles to players.
        roles = list(Role)
        shuffle(roles)
        self.players = [Player(id_, role, bus) for id_, (role, bus) in enumerate(zip(roles, buses))]
        # Create and shuffle the deck.
        self.deck = Card.create_deck()
        Card.shuffle_deck(self.deck)

    def run(self):
        for player in self.players:
            # Draw initial hands.
            player.draw_to_limit(self.deck)
            # Inform players of initial state.
            player.send_start_event(self.the_crown_id)

    @property
    def the_crown_id(self):
        return next(player for player in self.players if player.role == Role.THE_CROWN).id_
