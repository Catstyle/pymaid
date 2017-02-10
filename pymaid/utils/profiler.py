from inspect import ismodule

from line_profiler import LineProfiler


class Profiler(LineProfiler):
    """Enhance add_module

    usage:
        profiler.add_module(pymaid, add_submodule=True)
        ...
        profiler.print_stats()
    """

    def add_module(self, mod, add_submodule=False):
        super(Profiler, self).add_module(mod)
        for item in mod.__dict__.values():
            if ismodule(item):
                super(Profiler, self).add_module(item)

    def profile(self, func):
        self.add_function(func)


profiler = Profiler()
