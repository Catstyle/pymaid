import time
from collections import defaultdict
from functools import wraps

import numpy as np


class Profiler(object):

    def __init__(self):
        self.summaries = defaultdict(lambda: {'delays': [], 'total': 0})

    def print_summary(self, name=None, sort='delays', reverse=False):
        summaries = defaultdict(dict)
        for key in self.summaries:
            if name is None or name in self.summaries:
                summaries[key]['total'] = self.summaries[key]['total']
                summaries[key]['delays'] = np.array(self.summaries[key]['delays'])
            else:
                print 'no such summary:', name

        if not summaries:
            return

        if sort and sort not in ('total', 'delays'):
            print 'sort is specified but not in `("total", "delays")`'
            return

        keys = sorted(
            summaries.keys(),
            key=lambda key: summaries[key][sort] if sort == 'total' \
                            else summaries[key][sort].mean(),
            reverse=reverse
        )
        for func_name in keys:
            summary = summaries[func_name]
            array = summary['delays']
            print '#' * 30
            print 'func:', func_name
            print 'total:', summary['total']
            print 'succeeded:', len(array)
            if len(array) > 0:
                print 'min(ms):', array.min()
                print 'mean(ms):', array.mean()
                print 'max(ms):', array.max()
            print
default = Profiler()


def profiling(name, profiler=default):
    summary = profiler.summaries[name]
    def wrapper(func):
        @wraps(func)
        def _(*args, **kwargs):
            summary['total'] += 1
            start = float('%.6f' % (time.time() * 1000))
            resp = func(*args, **kwargs)
            delay = float('%.6f' % (time.time() * 1000 - start))
            summary['delays'].append(delay)
            return resp
        return _
    return wrapper
