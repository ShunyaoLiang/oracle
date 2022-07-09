from collections import namedtuple
from enum import Enum, auto
from random import shuffle
from threading import Thread
from typing import List
from queue import SimpleQueue

class Role(Enum):
    THE_CROWN = auto()
    DEMON_LORD = auto()
    USURPER = auto()
    KNIGHT = auto()
    CULTIST = auto()

class Card(Enum):
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

class Opcode(Enum):
    START = auto()

class Player:
    id_: int
    role: Role
    hand: List[Card]
    sender: SimpleQueue
    receiver: SimpleQueue

    hand_limit = 5

    def __init__(self, id_, receiver):
        self.id_ = id_
        self.hand = list()
        self.sender = SimpleQueue()
        self.receiver = receiver

    def draw(self, deck):
        while len(self.hand) < self.hand_limit:
            self.hand.append(deck.pop())

    def send_start_event(self, the_crown_id):
        self.send_event({
            'op': Opcode.START.value,
            'id': self.id_,
            'role': self.role.value,
            'the_crown_id': the_crown_id
        })

    def send_event(self, event):
        self.sender.put(event)

    def receive_event(self):
        return self.receiver.get()

class Game:
    players: List[Player]
    deck: List[Card]

    def __init__(self):
        self.players = list()
        self.deck = Card.create_deck()

    def add_player_from_sender(self, sender):
        # What the caller considers a sender is, to us, a receiver.
        receiver = sender
        if self.is_full:
            raise Exception('Tried to add a player to an ongoing game')
        player = Player(len(self.players), receiver)
        self.players.append(player)
        # Start the game once five players have joined
        if self.is_full:
            Thread(target=Game.run, args=(self,)).start()
        # Give the caller a way of receiving events.
        return player.sender

    def run(self):
        self.assign_player_roles()
        the_crown_id = next(player for player in self.players if player.role == Role.THE_CROWN).id_

        Card.shuffle_deck(self.deck)
        for player in self.players:
            # Draw initial hands.
            player.draw(self.deck)
            # Inform players of initial state.
            player.send_start_event(the_crown_id)

    def assign_player_roles(self):
        roles = list(Role)
        shuffle(roles)
        for player in self.players:
            player.role = roles.pop()

    @property
    def is_full(self):
        return len(self.players) == 5

Action = namedtuple('Action', [])
