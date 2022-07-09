from collections import namedtuple
from threading import Thread
from typing import List
from queue import SimpleQueue

class Player:
    sender: SimpleQueue
    receiver: SimpleQueue

    def __init__(self, receiver):
        self.sender = SimpleQueue()
        self.receiver = receiver

    def receive_event(self):
        return self.receiver.get()

class Game:
    players: List[Player]

    def __init__(self):
        self.players = list()

    def add_player_from_sender(self, sender):
        # What the caller considers a sender is, to us, a receiver.
        receiver = sender
        if self.is_full:
            raise Exception('Tried to add a player to an ongoing game')
        player = Player(receiver)
        self.players.append(player)
        # Start the game once five players have joined
        if self.is_full:
            Thread(target=Game.run, args=(self,)).start()
        # Give the caller a way of receiving events.
        return player.sender

    def run(self):
        pass

    @property
    def is_full(self):
        return len(self.players) == 5

Action = namedtuple('Action', [])
