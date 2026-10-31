"""Prefixed short IDs: ``dec_7f3a9c21``. Seed rows use fixed readable IDs instead (``dec_m1_platform``)."""

import secrets

PREFIXES = {"mtg", "dec", "tsk", "cfl", "rpl", "q", "run"}


def new_id(prefix: str) -> str:
    if prefix not in PREFIXES:
        raise ValueError(f"unknown id prefix {prefix!r}; expected one of {sorted(PREFIXES)}")
    return f"{prefix}_{secrets.token_hex(4)}"
