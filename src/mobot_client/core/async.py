import asyncio as aio
loop = aio.get_event_loop()

class Executor:
    """In most cases, you can just use the 'execute' instance as a
    function, i.e. y = await execute(f, a, b, k=c) => run f(a, b, k=c) in
    the executor, assign result to y. The defaults can be changed, though,
    with your own instantiation of Executor, i.e. execute =
    Executor(nthreads=4)"""
    def __init__(self, loop=loop, nthreads=1):
        from concurrent.futures import ThreadPoolExecutor
        self._ex = ThreadPoolExecutor(nthreads)
        self._loop = loop
    def __call__(self, f, *args, **kw):
        from functools import partial
        return self._loop.run_in_executor(self._ex, partial(f, *args, **kw))

execute = Executor()