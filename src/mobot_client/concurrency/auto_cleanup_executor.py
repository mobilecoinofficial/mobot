from concurrent.futures import ThreadPoolExecutor, Future, as_completed


class AutoCleanupExecutor(ThreadPoolExecutor):
    """Convenient wrapper for ThreadPoolExecutor that manages its own futures and ensures they're all finished."""
    def __init__(self, *args, **kwargs, ):
        super().__init__(*args, **kwargs)
        self._futures = set()

    def submit(self, fn, /,  *args, **kwargs):
        fut = super().submit(fn, *args, **kwargs)
        self._futures.add(fut)
        def done_callback(fut: Future):
            """Done callback removes from set of waiting futures"""
            fut.done()
            try:
                self._futures.remove(fut)
            except KeyError:
                print("No future found to clean up")
        fut.add_done_callback(done_callback)
        return fut

    def _finish(self):
        for future in as_completed(self._futures):
            future.done()
        self._futures = set()

    def shutdown(self, wait=True, *, cancel_futures=False) -> None:
        self._finish()
        super().shutdown(wait, cancel_futures=cancel_futures)