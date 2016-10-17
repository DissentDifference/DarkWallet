import itertools

class MultiMap:

    def __init__(self):
        self._items = {}

    def add(self, key, value):
        if not key in self._items:
            self._items[key] = []
        self._items[key].append(value)

    def remove(self, key, value):
        if not key in self._items:
            return False
        for item in self._items[key]:
            if item == value:
                self._items[key].remove(item)
        self._items = [item for item in self._items if item]
        return True

    def values(self):
        return itertools.chain.from_iterable(self._items.values())

    def find(self, key, compare_fn):
        if not key in self._items:
            return []
        return [value for value in self._items[key] if compare_fn(value)]

    def __iter__(self):
        return iter(self._items)

