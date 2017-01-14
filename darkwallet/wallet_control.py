import asyncio
import sys
import traceback

from libbitcoin import bc

class WalletControlProcess:

    def __init__(self, client, model):
        self._procs = [
            QueryBlockchainReorganizationProcess(self, client, model),
            ScanStealthProcess(self, client, model),
            ScanHistoryProcess(self, client, model),
            MarkConfirmedProcess(self, client, model),
            FillCacheProcess(self, client, model),
            GenerateKeysProcess(self, client, model)
        ]

    def wakeup_processes(self):
        [process.wakeup() for process in self._procs]

class BaseProcess:

    def __init__(self, parent, client, model):
        self.parent = parent
        self.client = client
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
            try:
                await self.update()
            except:
                traceback.print_exc()
                raise
            try:
                await asyncio.wait_for(self._wakeup_future, 5)
            except asyncio.TimeoutError:
                pass
            finally:
                self._wakeup_future = asyncio.Future()

    async def update(self):
        pass

class QueryBlockchainReorganizationProcess(BaseProcess):

    def __init__(self, parent, client, model):
        super().__init__(parent, client, model)

        self._max_rewind_depth = 50

    async def update(self):
        head = await self._query_blockchain_head()
        if head is None:
            return

        last_height, header = head
        index = last_height, header.hash()

        if self.model.compare_indexes(index):
            # Nothing changed.
            return
        print("Last height:", last_height)
        print("Current height:", self.model.current_height)

        if self.model.current_index is None:
            print("Initializing new chain state.")
        elif header.previous_block_hash == self.model.current_hash:
            print("New single block added.")
        elif await self._index_is_connected(index):
            print("Several new blocks added.")
        else:
            print("Blockchain reorganization event.")
            self._invalidate_records()

        self._record(index)

        # Wakeup the other processes.
        self.parent.wakeup_processes()

    async def _query_blockchain_head(self):
        ec, height = await self.client.last_height()
        if ec:
            print("Error: querying last_height:", ec, file=sys.stderr)
            return None
        ec, header = await self.client.block_header(height)
        if ec:
            print("Error: querying header:", ec, file=sys.stderr)
            return None
        header = bc.Header.from_data(header)
        return height, header

    async def _index_is_connected(self, index, current_recursions=1):
        # To avoid long rewinds, if we recurse too much
        # just treat it as a reorganization event.
        if current_recursions > self._max_rewind_depth:
            print("Exceeded max rewind depth.")
            return False

        height, hash_ = index
        print("Rewinding from:", index)

        if height <= self.model.current_height:
            print("Rewinded past current index.")
            return False

        ec, header = await self.client.block_header(height)
        if ec:
            print("Error: querying header:", ec, file=sys.stderr)
            return False
        header = bc.Header.from_data(header)

        if header.hash() != hash_:
            print("Error: non-matching header and index hash.",
                  file=sys.stderr)
            return False

        # Try to link this block with the current recorded hash.
        if header.previous_block_hash == self.model.current_hash:
            return True

        # Run the check for the next block along now.
        previous_index = height - 1, header.previous_block_hash

        return await self._index_is_connected(previous_index,
                                              current_recursions + 1)

    # ------------------------------------------------
    # Invalidate records because of reorganization.
    # ------------------------------------------------

    def _invalidate_records(self):
        print("Invalidating records...")
        self._clear_history()
        print("Cleared history.")
        self._nullify_address_updated_heights()
        print("Reset address updated heights.")

    def _clear_history(self):
        self.model.cache.history.clear()

    def _nullify_address_updated_heights(self):
        pass

    # ------------------------------------------------
    # Finish by writing the new current index.
    # ------------------------------------------------

    def _record(self, index):
        print("Updating current_index to:", index)
        self.model.current_index = index

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

