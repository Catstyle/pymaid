from hashlib import md5
from bisect import bisect


primes = (
    2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67, 71,
    73, 79, 83, 89, 97, 101, 103, 107, 109, 113, 127, 131, 137, 139, 149, 151,
    157, 163, 167, 173, 179, 181, 191, 193, 197, 199, 211, 223, 227, 229, 233,
    239, 241, 251, 257, 263, 269, 271, 277, 281, 283, 293, 307, 311, 313, 317,
    331, 337, 347, 349, 353, 359, 367, 373, 379, 383, 389, 397, 401, 409, 419,
    421, 431, 433, 439, 443, 449, 457, 461, 463, 467, 479, 487, 491, 499, 503,
    509, 521, 523, 541, 547, 557, 563, 569, 571, 577, 587, 593, 599, 601, 607,
    613, 617, 619, 631, 641, 643, 647, 653, 659, 661, 673, 677, 683, 691, 701,
    709, 719, 727, 733, 739, 743, 751, 757, 761, 769, 773, 787, 797, 809, 811,
    821, 823, 827, 829, 839, 853, 857, 859, 863, 877, 881, 883, 887, 907, 911,
    919, 929, 937, 941, 947, 953, 967, 971, 977, 983, 991, 997
)


def md5_hash_func(key):
    return int(md5(key).hexdigest(), 16)


class HashNode(object):

    def __init__(self, key, weight=16, enabled=True):
        self.key = key
        self.hashed_key = md5_hash_func(key)
        self.weight = weight
        self.enabled = enabled

    def __eq__(self, other):
        if not isinstance(other, HashNode):
            return NotImplemented
        return self.hashed_key == other.hashed_key

    def __ne__(self, other):
        return self != other

    def __hash__(self):
        return self.hashed_key


class BaseHashManager(object):

    def __init__(self, name, hash_func=md5_hash_func):
        self.name = name
        self.objects = {}
        self.nodes = []
        self.hash_func = hash_func

    def add_node(self, node):
        if node.key in self.objects:
            return
        self.objects[node.key] = node
        node._hash_manager = self
        if node.enabled:
            self.nodes.append(node)
            self.rehash()

    def add_nodes(self, nodes):
        for node in nodes:
            if node.key not in self.objects:
                self.objects[node.key] = node
                node._hash_manager = self
                if node.enabled:
                    self.nodes.append(node)
        self.rehash()

    def remove_node(self, node):
        if node.key in self.objects:
            del self.objects[node.key]
            node._hash_manager = None
            del node._hash_manager
        if node in self.nodes:
            self.nodes.remove(node)
        self.rehash()

    def enable_node(self, key):
        if key not in self.objects:
            return
        node = self.objects[key]
        node.enabled = True
        if node not in self.nodes:
            self.nodes.append(node)
            self.rehash()

    def disable_node(self, key):
        if key not in self.objects:
            return
        node = self.objects[key]
        node.enabled = False
        if node in self.nodes:
            self.nodes.remove(node)
            self.rehash()

    def reset(self):
        self.objects.clear()
        del self.nodes[:]

    def rehash(self):
        raise NotImplementedError

    def get_node(self, key):
        raise NotImplementedError

    def clone(self):
        # return a copy of this manager
        raise NotImplementedError

    def __str__(self):
        return '<{}: {}>'.format(self.__class__.__name__, self.name)


class HashRing(BaseHashManager):

    def __init__(self, name, hash_func=md5_hash_func):
        super(HashRing, self).__init__(name, hash_func)
        self.lookup_table = {}
        self.sorted_keys = []

    def rehash(self):
        self.lookup_table = {}
        self.sorted_keys = []

        if not self.nodes:
            return

        self.lookup_table = {}
        self.sorted_keys = []

        hash_func = self.hash_func
        lookup_table = self.lookup_table
        for node in self.nodes:
            key = node.key
            for idx in range(node.weight):
                virtual_key = hash_func('%s-%s' % (key, idx))
                if virtual_key in lookup_table:
                    # TODO: what to do?
                    continue
                lookup_table[virtual_key] = node
        self.sorted_keys = sorted(lookup_table.keys())

    def get_node(self, key):
        if not self.nodes:
            return

        virtual_key = self.hash_func(key)
        skeys = self.sorted_keys
        pos = bisect(skeys, virtual_key)
        return self.lookup_table[skeys[pos if pos < len(skeys) else 0]]

    def reset(self):
        super(HashRing, self).reset()
        self.lookup_table.clear()
        del self.sorted_keys[:]

    def clone(self):
        obj = self.__class__(self.name, self.hash_func)
        obj.objects = self.objects.copy()
        obj.nodes = self.nodes[:]
        obj.lookup_table = self.lookup_table.copy()
        obj.sorted_keys = self.sorted_keys[:]
        return obj


class MaglevHash(BaseHashManager):

    def __init__(self, name, hash_func=md5_hash_func, virtual_entry_count=16):
        super(MaglevHash, self).__init__(name, hash_func)
        self.virtual_entry_count = virtual_entry_count
        self.lookup_table_size = 0
        self.lookup_table = []

    def rehash(self):
        self.lookup_table = []
        self.lookup_table_size = 0

        if not self.nodes:
            return

        permutation = []
        hash_func = self.hash_func
        entry_count = len(self.nodes) * self.virtual_entry_count
        pos = bisect(primes, entry_count)
        entry_count = primes[pos if pos < len(primes) else -1]
        self.lookup_table_size = entry_count
        for node in self.nodes:
            key = node.key
            offset = hash_func('cat' + key) % entry_count
            skip = (hash_func('lee' + key) % (entry_count - 1)) + 1
            permutation.append([
                (offset + idx * skip) % entry_count
                for idx in range(entry_count)
            ])

        nexts = [0] * len(self.nodes)
        entries = self.lookup_table = [-1] * entry_count

        n = 0
        while 1:
            for idx in range(len(self.nodes)):
                c = permutation[idx][nexts[idx]]
                while entries[c] != -1:
                    nexts[idx] += 1
                    c = permutation[idx][nexts[idx]]
                entries[c] = idx
                nexts[idx] += 1
                n += 1

                if n == entry_count:
                    return

    def get_node(self, key):
        if not self.lookup_table:
            return
        key = self.hash_func('cat' + key)
        return self.nodes[self.lookup_table[key % self.lookup_table_size]]

    def reset(self):
        super(MaglevHash, self).reset()
        del self.lookup_table[:]
        self.lookup_table_size = 0

    def clone(self):
        obj = self.__class__(self.name, self.hash_func)
        obj.objects = self.objects.copy()
        obj.nodes = self.nodes[:]
        obj.lookup_table = self.lookup_table[:]
        obj.lookup_table_size = self.lookup_table_size
        obj.virtual_entry_count = self.virtual_entry_count
        return obj
