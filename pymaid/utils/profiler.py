from line_profiler import LineProfiler


class Profiler(LineProfiler):

    def enable_all(self):
        ''' enable profiler with pymaid injection'''
        import pymaid
        self.add_module(pymaid)
        self.enable_by_count()

    def profile(self, func):
        self.add_function(func)


profiler = Profiler()
