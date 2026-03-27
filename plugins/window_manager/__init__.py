"""Window Manager — vim-style window snapping and movement.

Binds Ctrl+Cmd + h/j/k/l/r/w/e to snap, center, and move
the focused window across screens.
"""

# Default key bindings: (hotkey, action)
_BINDINGS = [
    ("ctrl+cmd+h", ("snap", "left")),
    ("ctrl+cmd+l", ("snap", "right")),
    ("ctrl+cmd+k", ("snap", "top")),
    ("ctrl+cmd+j", ("snap", "bottom")),
    ("ctrl+cmd+r", ("snap", "full")),
    ("ctrl+cmd+w", ("center",)),
    ("ctrl+cmd+e", ("move_to_screen", "next")),
]


def setup(wz):
    """Entry point called by the ScriptEngine plugin loader."""
    for hotkey, action in _BINDINGS:
        if action[0] == "snap":
            position = action[1]
            wz.hotkey.bind(hotkey, lambda p=position: wz.window.snap(p))
        elif action[0] == "center":
            wz.hotkey.bind(hotkey, lambda: wz.window.center())
        elif action[0] == "move_to_screen":
            direction = action[1]
            wz.hotkey.bind(hotkey, lambda d=direction: wz.window.move_to_screen(d))
