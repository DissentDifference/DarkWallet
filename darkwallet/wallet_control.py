import asyncio

class WalletControlProcess:

    def __init__(self, model):
        self._procs = [
            QueryBlockchainReorganizationProcess(self, model),
            ScanStealthProcess(self, model),
            ScanHistoryProcess(self, model),
            MarkConfirmedProcess(self, model),
            FillCacheProcess(self, model),
            GenerateKeysProcess(self, model)
        ]

    def wakeup(self):
        [process.wakeup() for process in self._procs]

class BaseProcess:

    def __init__(self, parent, model):
        self.parent = parent
        self.model = model

        self._wakeup_future = asyncio.Future()
        self._start()

    def _start(self):
        loop = asyncio.get_event_loop()
        self._task = loop.create_task(self._run())

    def wakeup(self):
        self._wakeup_future.set_result(None)

    async def _run(self):
        while True:
            await self.update()
            try:
                await asyncio.wait_for(self._wakeup_future, 5)
                print("Woke up!")
            except asyncio.TimeoutError:
                print("Timeout.")
            finally:
                self._wakeup_future = asyncio.Future()

    async def update(self):
        pass

class QueryBlockchainReorganizationProcess(BaseProcess):

    async def update(self):
        print("Update.")

class ScanStealthProcess(BaseProcess):

    async def update(self):
        pass

class ScanHistoryProcess(BaseProcess):

    async def update(self):
        pass

class MarkConfirmedProcess(BaseProcess):

    async def update(self):
        pass

class FillCacheProcess(BaseProcess):

    async def update(self):
        pass

class GenerateKeysProcess(BaseProcess):

    async def update(self):
        pass

