from threading import Thread

from .game import Game
from .bus import Bus


class Lobby:
    buses: list[Bus]

    def __init__(self):
        self.buses = []

    def join(self) -> Bus:
        if self.is_full:
            raise Exception('Tried to join a full lobby')
        ours, theirs = Bus.create_pair()
        self.buses.append(ours)
        # Start the game once five players have joined.
        if self.is_full:
            game = Game(self.buses)
            Thread(target=Game.run, args=(game,)).start()
        # Give the caller a way of receiving events.
        return theirs


    @property
    def is_full(self):
        return len(self.buses) == 5
