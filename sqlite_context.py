"""A committed SQLite context that also releases Windows file handles immediately."""
from contextlib import contextmanager
import sqlite3


@contextmanager
def connection(*args, **kwargs):
    db=sqlite3.connect(*args,**kwargs)
    try:
        with db:
            yield db
    finally:
        db.close()
