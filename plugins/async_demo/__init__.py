"""Async Demo — verify all async/await scripting features.

Registers launcher commands (> async-*) that exercise each async
capability: async def callbacks, lambda coroutines, async timers,
async events, wz.run(), concurrent tasks, and error logging.
"""


def setup(wz):
    """Entry point called by the ScriptEngine plugin loader."""
    from .commands import register

    register(wz)
