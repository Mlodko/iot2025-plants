from datetime import datetime, timedelta
from typing import Callable
import uuid
import asyncio

class ScheduledEvent:
    """
    Represents a single scheduled event.

    Attributes
    ----------
    id
        Unique identifier for the event.
    creation_time
        Time when the event object was created.
    execution_time
        Next scheduled execution datetime for the event.
    action
        A callable to be executed when the event fires. Must be synchronous
        and non-blocking (the scheduler executes it directly).
    repeat_interval
        If provided, the event is repeating and ``execution_time`` is advanced
        by this timedelta after each execution.
    executed
        True when a non-repeating event has been executed (used by the scheduler).

    Notes
    -----
    If you need arguments for the action callable, bind them in a closure or
    use a lambda. Example (shown as a syntax-highlighted code block):

    .. code-block:: python

        def foo(bar: str, baz: int) -> None:
            print(f"foo({bar}, {baz})")

        my_bar: str = "hello"
        my_baz: int = 42
        event = ScheduledEvent(
            datetime.now(),
            lambda: foo(my_bar, my_baz),
            timedelta(hours=21, minutes=37)
        )
    """
    def __init__(self, time: datetime, action: Callable[[], None], repeat_interval: timedelta | None = None) -> None:
        """
        Create a :class:`ScheduledEvent`.

        :param time: The datetime at which the event should first execute.
        :type time: datetime
        :param action: Callable with no parameters to run when the event fires.
        :type action: Callable[[], None]
        :param repeat_interval: Optional timedelta that, if provided, makes the
            event repeating. After each execution ``execution_time`` will be
            incremented by this interval.
        :type repeat_interval: timedelta | None
        """
        self.id: uuid.UUID = uuid.uuid4()
        self.creation_time: datetime = datetime.now()
        self.execution_time: datetime = time
        self.action: Callable[[], None] = action
        self.repeat_interval: timedelta | None = repeat_interval
        self.executed: bool = False
        
    def execute(self) -> None:
        """
        Execute the event's action.

        Behaviour
        ---------
        - Calls the ``action`` callable.
        - If ``repeat_interval`` is set, advances ``execution_time`` by that interval.
        - Otherwise marks ``executed = True``.

        Notes
        -----
        Exceptions raised by ``action`` are not handled here; the scheduler
        surrounds :meth:`execute` with a try/except to avoid terminating the loop.
        Actions should ideally be lightweight and non-blocking. If you need to
        run async or long-running work, schedule it from inside the action.
        """
        self.action()
        if self.repeat_interval:
            self.execution_time += self.repeat_interval
        else:
            self.executed = True
            
    def __lt__(self, other: 'ScheduledEvent') -> bool:
        """
        Comparison operator used for ordering events by their next execution time.

        :param other: Another ScheduledEvent to compare against.
        :type other: ScheduledEvent
        :returns: True if this event's ``execution_time`` is earlier than ``other``'s.
        :rtype: bool

        This method is used when sorting the internal events list.
        """
        return self.execution_time < other.execution_time
            
class Scheduler:
    """
    Simple asynchronous scheduler that runs :class:`ScheduledEvent` instances.

    Usage
    -----
    - Create an instance.
    - Use :meth:`start` to create the background task running :meth:`run`.
    - Add / remove events with :meth:`add_event` and :meth:`remove_event`.
    - Call :meth:`stop` to stop the scheduler and await termination.

    Concurrency and semantics
    -------------------------
    - The scheduler uses an asyncio-based cooperative model (single-threaded event loop).
    - ``queue_lock`` protects the ``events`` list for concurrent mutation by other coroutines.
    - ``_wakeup`` is an :class:`asyncio.Event` used to wake the scheduler when the queue
      changes (new event, removal, stop).
    - The scheduler re-checks the head of the queue under ``queue_lock`` to avoid races
      around clearing ``_wakeup`` and waiting for a timeout.
    - For many events, replacing the sorted list with a heap (``heapq``) is advised
      for performance (O(log n) inserts/pops).
    """
    def __init__(self) -> None:
        """
        Initialize the Scheduler.

        Initial state:
        - ``events`` is empty.
        - ``queue_lock`` is an asyncio lock protecting ``events``.
        - ``_wakeup`` is the event used to interrupt the scheduler wait.
        - ``running`` is False until :meth:`start` or :meth:`run` sets it.
        - ``_scheduler_task`` stores the background :class:`asyncio.Task` created by :meth:`start`.
        """
        self.events: list[ScheduledEvent] = []
        self.queue_lock: asyncio.Lock = asyncio.Lock()
        self._wakeup: asyncio.Event = asyncio.Event()
        self.running: bool = False
        self._scheduler_task: asyncio.Task[None] | None = None
    
    def start(self) -> None:
        """
        Launch the scheduler ``run()`` loop as a background task.

        - Idempotent: subsequent calls do nothing while the task is already running.
        - This method does not block; it schedules :meth:`run` on the current event loop.
        """
        if self._scheduler_task is None or self._scheduler_task.done():
            self._scheduler_task = asyncio.create_task(self.run())
    
    async def stop(self) -> None:
        """
        Stop the scheduler and wait for the background task to finish.

        Behaviour
        ---------
        - Sets ``running = False`` and wakes the run loop via ``_wakeup.set()`` so it
          exits promptly.
        - Awaits the scheduler task (if present) to ensure the run loop has terminated.

        Notes
        -----
        This method should be awaited to ensure the scheduler has completely stopped.
        """
        self.running = False
        self._wakeup.set()
        if self._scheduler_task is not None:
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                # Preserve the cancellation semantics while ensuring cleanup
                pass
            self._scheduler_task = None
    
    async def add_event(self, event: ScheduledEvent) -> None:
        """
        Add an event to the schedule.

        :param event: The :class:`ScheduledEvent` instance to schedule.
        :type event: ScheduledEvent

        Behaviour
        ---------
        - The event is appended and the internal list is sorted by execution time.
        - Wakes the scheduler so it can re-evaluate the next deadline.
        - This method acquires ``queue_lock`` briefly and is safe to call concurrently.
        """
        async with self.queue_lock:
            self.events.append(event)
            self.events.sort()
        # Wake the loop so it can re-evaluate the head
        self._wakeup.set()
        
    async def remove_event(self, event_id: uuid.UUID) -> None:
        """
        Remove an event by ``id``.

        :param event_id: The UUID of the event to remove.
        :type event_id: uuid.UUID

        Behaviour
        ---------
        - If no matching event exists, the call is a no-op.
        - Wakes the scheduler so it can re-evaluate the head in case the removed
          event was the next to run.
        """
        async with self.queue_lock:
            self.events = [event for event in self.events if event.id != event_id]
        self._wakeup.set()
        
    async def run(self):
        """
        The scheduler loop.

        Main loop behaviour
        -------------------
        - Marks ``running = True`` and repeatedly:
            1. Reads the head event under ``queue_lock``.
            2. If no events exist, waits on ``_wakeup`` until an event is added or stop is called.
            3. Otherwise computes the time until the head is due.
            4. Clears ``_wakeup``, re-checks the head under ``queue_lock`` (defensive
               step to avoid losing a wake that occurred before clear), and recomputes
               remaining wait time.
            5. Waits either for ``_wakeup`` (queue changed or stop) or until timeout.
               - If woken early: loop repeats to recompute head.
               - If timeout elapses: the candidate event should be due; pop it under lock,
                 execute its action (outside lock) and reinsert it if it's repeating.

        Notes
        -----
        - ``action`` exceptions are caught so that a faulty action doesn't kill the scheduler.
        - The method returns when ``running`` becomes False (stop requested) and the loop exits.
        """
        self.running = True
        try:
            while self.running:
                # Get current head of event queue
                async with self.queue_lock:
                    next_event = self.events[0] if self.events else None
                
                if next_event is None:
                    # No events -> wait until someone wakes us (add/remove/stop)
                    _ = await self._wakeup.wait()
                    self._wakeup.clear()
                    continue
                
                # Compute how long until the head is due
                now = datetime.now()
                seconds_until_next_event = max(0.0, (next_event.execution_time - now).total_seconds())
                
                # Clear wake flag and re-check the head under lock to avoid losing a wake that happened before clear
                self._wakeup.clear()
                async with self.queue_lock:
                    if not self.events:
                        continue
                    head = self.events[0]
                    # If head changed while we cleared, re-loop and recompute
                    if head.id != next_event.id:
                        continue
                    # Recompute remaining wait time in case time passed
                    seconds_until_next_event = max(0.0, (head.execution_time - datetime.now()).total_seconds())
                
                try:
                    # Wait until either the head's time elapses or someone sets the wakeup
                    _ = await asyncio.wait_for(self._wakeup.wait(), timeout=seconds_until_next_event)
                    # Woken up early -> re-loop to re-evaluate queue
                    continue
                except asyncio.TimeoutError:
                    # Timeout expired -> candidate should be due; confirm and pop under lock
                    async with self.queue_lock:
                        if not self.events:
                            continue
                        candidate = self.events[0]
                        if candidate.id != next_event.id:
                            # head changed -> skip
                            continue
                        event = self.events.pop(0)

                    # Execute outside the lock; protect against exceptions
                    try:
                        event.execute()
                    except Exception:
                        # TODO: log the exception; don't let scheduler die
                        pass

                    # If repeating, reinsert under lock
                    if not event.executed:
                        async with self.queue_lock:
                            self.events.append(event)
                            self.events.sort()
                        self._wakeup.set()
        finally:
            self.running = False
