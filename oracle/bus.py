from queue import SimpleQueue
from typing import Any, NamedTuple


class Bus(NamedTuple):
    sender: SimpleQueue
    receiver: SimpleQueue

    @staticmethod
    def create_pair() -> tuple['Bus', 'Bus']:
        left = SimpleQueue()
        right = SimpleQueue()
        return (Bus(left, right), Bus(right, left))

    def send(self, event: Any):
        self.sender.put(event)

    def receive(self):
        return self.receiver.get()

class Action(NamedTuple):
    pass
