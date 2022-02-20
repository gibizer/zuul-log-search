import datetime


def now() -> datetime.datetime:
    # needs to wrap it, so we can mock in during test
    return datetime.datetime.now()
