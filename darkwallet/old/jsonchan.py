import time
import math
import logging
import traceback
from collections import defaultdict

VALID_SECTIONS = ['b', 'coinjoin', 'tmp', 'chat', 'identity', 'i']
MAX_THREADS = 2000
MAX_POSTS = 200
MAX_DATA_SIZE = 20000

class DataTooBigError(Exception):
    def __str__(self):
        return  "Data is too big"
class InvalidSectionError(Exception):
    def __str__(self):
        return "Invalid section, valid are: " + ", ".join(VALID_SECTIONS)
class MissingThread(Exception):
    def __str__(self):
        return "Thread doesnt exist"
class ClientGone(Exception):
    def __str__(self):
        return "Client is gone"
class IncorrectThreadId(Exception):
    def __str__(self):
        return "Thread id must be alphanumeric"

class JsonChanSection(object):
    max_threads = MAX_THREADS
    subscriptions = defaultdict(list)
    def __init__(self, name):
        self._name = name
        self._threads = {}

    def subscribe(self, thread_id, callback):
        self.subscriptions[thread_id].append(callback)

    def unsubscribe(self, thread_id, callback):
        if callback in self.subscriptions[thread_id]:
            self.subscriptions[thread_id].remove(callback)

    def notify_subscribers(self, thread_id, data):
        failed = []
        for callback in list(self.subscriptions[thread_id]):
            try:
                callback(data)
            except Exception as e:
                print("Failed callback", e)
                traceback.print_exc()
                failed.append(callback)
        # remove failed
        for callback in list(failed):
            self.subscriptions[thread_id].remove(callback)

    def find_last_thread(self):
        sel_thread_id = list(self._threads.keys())[0]
        first_thread = self._threads[sel_thread_id]
        timestamp = first_thread['timestamp']
        for thread_id, thread in self._threads.items():
            if thread['timestamp'] < timestamp:
                timestamp = thread['timestamp']
                sel_thread_id = thread_id
        return sel_thread_id

    def purge_threads(self):
        while len(self._threads) > self.max_threads:
            last_thread = self.find_last_thread()
            try:
                self._threads.pop(last_thread)
            except KeyError:
                pass # already deleted

    def post(self, thread_id, data):
        if len(data) > MAX_DATA_SIZE:
            raise DataTooBigError()
        if not thread_id.isalnum():
            raise IncorrectThreadId()
        if thread_id in self._threads:
            thread = self._threads[thread_id]
            thread['posts'].append(data)
            if len(thread['posts']) > MAX_POSTS:
                thread['posts'].pop(0)
            thread['timestamp'] = time.time()
        else:
            thread = {'timestamp': time.time(), 'posts': [data]}
            self._threads[thread_id] = thread
        self.purge_threads()
        self.notify_subscribers(thread_id, {'thread': thread_id, 'data': data, 'timestamp': thread['timestamp']})
        return thread

    def get_thread(self, thread_id):
        if thread_id in self._threads:
            return self._threads[thread_id]
        raise MissingThread()

    def get_threads(self):
        return self._threads.keys()

class JsonChan(object):
    def __init__(self):
        self._sections = {}

    def post(self, section_name, thread_id, data):
        section = self.get_section(section_name)
        return section.post(thread_id, data)

    def get_threads(self, section_name):
        section = self.get_section(section_name)
        return section.get_threads()

    def get_section(self, name):
        if not name in self._sections:
            if name in VALID_SECTIONS:
                self._sections[name] = JsonChanSection(name)
            else:
                raise InvalidSectionError()
        return self._sections[name]

class JsonChanHandlerBase(object):

    def __init__(self, handler, request_id, json_chan, darkwallet):
        self._handler = handler
        self._request_id = request_id
        self._json_chan = json_chan
        self._darkwallet = gateway

    def process_response(self, error, raw_result):
        assert error is None or type(error) == str
        result = self.translate_response(raw_result)
        response = {
            "id": self._request_id,
            "result": result
        }
        if error:
            response["error"] = error
        self._handler.queue(response)

    def process(self, params):
        print("process jsonchan req", self._json_chan)
        self.process_response(None, {'result': 'ok'})

    def translate_arguments(self, params):
        return params

    def translate_response(self, result):
        return result

class ObJsonChanPost(JsonChanHandlerBase):
    def process(self, params):
        self._json_chan.post(params[0], params[1], params[2])
        self.process_response(None, {'result': 'ok', 'method': 'post'})
        self._darkwallet.send_p2p(params);

class ObJsonChanList(JsonChanHandlerBase):
    def process(self, params):
        threads = self._json_chan.get_threads(params[0])
        self.process_response(None, {'result': 'ok', 'method': 'list', 'threads': threads})

class ObJsonChanGet(JsonChanHandlerBase):
    def process(self, params):
        thread = self._json_chan.get_section(params[0]).get_thread(params[1])
        self.process_response(None, {'result': 'ok', 'method': 'get', 'thread': thread})

class ObJsonChanSubscribe(JsonChanHandlerBase):
    def process(self, params):
        self._params = params
        section = self._json_chan.get_section(params[0])
        section.subscribe(params[1], self.send_notification)
        # store in handler memory to be able to unsubscribe
        if not params[1] in self._handler._subscriptions['channel']:
            self._handler._subscriptions['channel'][params[1]] = []
        self._handler._subscriptions['channel'][params[1]].append([params[0], self.send_notification])
        self.process_response(None, {'result': 'ok', 'method': 'subscribe', 'thread': params[1]})

    def send_notification(self, data):
        data['type'] = 'chan_update'
        if not self._handler.ws_connection or not self._handler._connected:
            raise ClientGone()
            #section = self._json_chan.get_section(self._params[0])
            #section.unsubscribe(self._params[1], self.send_notification)
        self._handler.queue(data)

class ObJsonChanUnsubscribe(JsonChanHandlerBase):
    def process(self, params):
        self._params = params
        section = self._json_chan.get_section(params[0])
        thread_id = params[1]
        if thread_id in self._handler._subscriptions['channel']:
            i = 0
            to_remove = []
            for section_name, cb in self._handler._subscriptions['channel'][thread_id]:
                if section_name == params[0]:
                    section.unsubscribe(thread_id, cb)
                    to_remove.append(i)
                i += 1
            toremove.reverse()
            for idx in toremove:
                self._handler._subscriptions['channel'][thread_id].pop(idx) 
            self.process_response(None, {'result': 'ok', 'method': 'unsubscribe', 'thread': params[1]})
        else:
            self.process_response(None, {'result': 'error', 'error': 'Thread does not exist', 'thread': params[1]})
 
class ObDisconnectClient(JsonChanHandlerBase):
    def process(self, params):
        for thread_id in self._handler._subscriptions['channel']:
            for section_name, cb in self._handler._subscriptions['channel'][thread_id]:
                section = self._json_chan.get_section(section_name)
                section.unsubscribe(thread_id, cb)
 
        self._handler._subscriptions['channel'] = {}


class JsonChanHandler:

    handlers = {
        "chan_post":                ObJsonChanPost,
        "chan_list":                ObJsonChanList,
        "chan_get":                 ObJsonChanGet,
        "chan_subscribe":           ObJsonChanSubscribe,
        "chan_unsubscribe":         ObJsonChanUnsubscribe,
        "disconnect_client":        ObDisconnectClient
    }

    def __init__(self, p2p):
        self._json_chan = JsonChan()
        self._p2p = p2p
        p2p.add_callback('jsonchan', self.on_p2p_message)

    def send_p2p(self, params):
        msg = {'type': 'jsonchan', 'action': 'post', 'data': params}
        self._p2p.send(msg, secure=True)

    def on_p2p_message(self, data):
        if data.get('action') == 'post' and data.get('data'):
            params = data.get('data')
            if len(params) == 3:
                self._json_chan.post(params[0], params[1], params[2])

    def handle_request(self, socket_handler, request):
        command = request["command"]
        if command not in self.handlers:
            return False
        params = request["params"]
        # Create callback handler to write response to the socket.
        handler = self.handlers[command](socket_handler, request["id"], self._json_chan, self)
        try:
            params = handler.translate_arguments(params)
        except Exception as exc:
            logging.error("Bad parameters specified: %s", exc, exc_info=True)
            return True
        try:
            handler.process(params)
        except Exception as e:
            handler.process_response(str(e), {})
        return True

if __name__ == '__main__':
    site = JsonChan()
    first_thread = site.post('b', 'first', "fooo!")
    for idx1 in range(1000):
        site.post('b', 'first', "more!")
        for idx2 in range(100):
            site.post('b', 'myid'+str(idx1)+'x'+str(idx2), "{'a': 'b'}")
    print(len(site.get_section('b').get_threads()), site.get_section('b').get_thread('first'))
