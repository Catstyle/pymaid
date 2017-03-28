from hashlib import md5
from bisect import bisect


def md5_hash_func(key):
    return int(md5(key).hexdigest(), 16)


class HashNode(object):

    def __init__(self, key, weight=1):
        self.key = key
        self.hashed_key = md5_hash_func(key)
        self.weight = weight

    def __eq__(self, other):
        if not isinstance(other, HashNode):
            return NotImplemented
        return self.hashed_key == other.hashed_key

    def __ne__(self, other):
        return self != other

    def __hash__(self):
        return self.hashed_key


class HashRing(object):

    def __init__(self, hash_func=md5_hash_func, virtual_entry_count=16):
        self.nodes = {}
        self.sorted_keys = []
        self.hash_func = hash_func
        self.virtual_entry_count = virtual_entry_count

    def add_node(self, node):
        key = node.key
        hash_func = self.hash_func
        for idx in range(self.virtual_entry_count):
            virtual_key = hash_func('%s-%s' % (key, idx))
            if virtual_key in self.nodes:
                # TODO: what to do?
                continue
            self.nodes[virtual_key] = node
        self.sorted_keys = sorted(self.nodes.keys())

    def add_nodes(self, nodes):
        for node in nodes:
            self.add_node(node)

    def get_node_by_key(self, key):
        if not self.nodes:
            return
        virtual_key = self.hash_func(key)
        skeys = self.sorted_keys
        pos = bisect(skeys, virtual_key)
        return self.nodes[skeys[pos if pos < len(skeys) else 0]]


class MaglevHash(object):

    def __init__(self, nodes, lookup_table_size, hash_func=md5_hash_func):
        self.nodes = nodes
        self.lookup_table = []
        self.lookup_table_size = lookup_table_size
        self.hash_func = hash_func
        self.rehash()

    def rehash(self):
        if not self.nodes:
            return

        permutation = []
        hash_func = self.hash_func
        lookup_table_size = self.lookup_table_size
        for node in self.nodes:
            key = node.key
            offset = hash_func('cat' + key) % lookup_table_size
            skip = (hash_func('lee' + key) % (lookup_table_size - 1)) + 1
            permutation.append([
                (offset + idx * skip) % lookup_table_size
                for idx in range(lookup_table_size)
            ])

        nexts = [0] * len(self.nodes)
        entries = self.lookup_table = [-1] * lookup_table_size

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

                if n == lookup_table_size:
                    return

    def add_node(self, node):
        if node in self.nodes:
            return
        self.nodes.append(node)
        self.rehash()

    def add_nodes(self, nodes):
        for node in nodes:
            if node not in self.nodes:
                self.nodes.append(node)
        self.rehash()

    def remove_node(self, node):
        if node not in self.nodes:
            return

        self.nodes.remove(node)
        self.rehash()

    def get_node_by_key(self, key):
        if not self.lookup_table:
            return
        key = self.hash_func('cat' + key)
        return self.nodes[self.lookup_table[key % self.lookup_table_size]]
