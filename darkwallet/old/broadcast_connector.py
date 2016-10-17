import zmq
import struct
import config
from twisted.internet import reactor

class BroadcastConnector(object):
    def __init__(self):
        self.c = zmq.Context()
        self.task = None
        self.watchdog_task = None
        self.queue = []
        self.callback = None
        self.tries = 0

    def broadcast(self, tx, cb):
        self.queue.append([tx, cb])
        if not self.task:
            self.next(1)

    def receive(self):
        self.tries += 1
        try:
            data = self.s.recv(flags=zmq.NOBLOCK)
            retcode = struct.unpack("<B", data)[0]
            self.watchdog_task.cancel()
            self.watchdog_task = None
            self.task = None
            self.answer(None, retcode)
            self.next(1)
        except Exception as e:
            #print "except", e
            self.task = reactor.callLater(0.08, self.receive)

    def next(self, timeout):
        if not self.queue:
            return
        self.current = self.queue.pop(0)
        msg = self.current[0]
        self.watchdog_task = reactor.callLater(timeout, self.watchdog)
        # new socket
        self.s = self.c.socket(zmq.REQ)
        self.s.connect(config.get("broadcaster-url", "tcp://localhost:9109"))
        self.s.send(msg)
        self.tries = 0
        self.receive()

    def answer(self, error, data=None):
        print "broadcaster answer", error, data, self.tries
        self.current[1](self.current[0], error, data)
        self.current = None
        self.s.close()

    def watchdog(self):
        self.watchdog_task = None
        if self.task:
            self.task.cancel()
            self.task = None
            self.answer("timeout")
            self.next(1)


if __name__ == '__main__':
    def answer(tx, error, data):
        print "ANSWER",tx, error, data

    con = BroadcastConnector()
    con.broadcast("000111", answer)
    con.broadcast("0001112", answer)
    con.broadcast("0001113", answer)
    con.broadcast("0001114", answer)

    reactor.run()
