import sys
try:
    import GreenletProfile as Profiler
except ImportError:
    sys.stdout.write(
        'GreenletProfile is not found, recommend to install it for better '
        'profile precision, try `pip install greenletprofile` '
        '(not available for pypy yet)\n'
    )
    greenlet_profile = False
    import cProfile as Profiler
    import StringIO
    import pstats


class ProfilerContext(object):

    def __enter__(self):
        if greenlet_profile:
            Profiler.set_clock_type('cpu')
            Profiler.start()
        else:
            self.pr = Profiler.Profile()
            self.pr.enable()

    def __exit__(self, type, value, traceback):
        if greenlet_profile:
            Profiler.stop()
            stats = Profiler.get_func_stats()
            stats.print_all()
        else:
            self.pr.disable()
            s = StringIO.StringIO()
            sortby = 'cumulative'
            ps = pstats.Stats(self.pr, stream=s).sort_stats(sortby)
            ps.print_stats()
            sys.stdout.write(s.getvalue())
