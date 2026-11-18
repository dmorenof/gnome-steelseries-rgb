"""Bounded JSON reads and atomic, cooperatively locked user-data writes."""

import fcntl
import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path

MAX_JSON_BYTES = 1024 * 1024


class StorageError(RuntimeError):
    """User data cannot be safely read or replaced."""


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def decode_json(raw):
    def invalid_constant(value):
        raise ValueError(f"Invalid JSON number: {value}")

    try:
        return json.loads(raw, object_pairs_hook=_unique_object, parse_constant=invalid_constant)
    except (ValueError, UnicodeError, RecursionError) as error:
        raise StorageError("Invalid JSON data.") from error


def read_bytes(path, limit=MAX_JSON_BYTES):
    try:
        with Path(path).open("rb") as stream:
            raw = stream.read(limit + 1)
    except FileNotFoundError:
        return None
    if len(raw) > limit:
        raise StorageError(f"JSON file exceeds {limit} bytes.")
    return raw


def read_json(path, default):
    raw = read_bytes(path)
    return default if raw is None else decode_json(raw)


@contextmanager
def file_lock(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_name(path.name + ".lock").open("a") as stream:
        os.chmod(stream.name, 0o600)
        fcntl.flock(stream, fcntl.LOCK_EX)
        yield


def write_bytes(path, raw):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def create_bytes(path, raw):
    """Create a private file exclusively and remove an incomplete creation."""
    path = Path(path)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def encode_json(data):
    raw = (json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
    if len(raw) > MAX_JSON_BYTES:
        raise StorageError("JSON data exceeds the supported size.")
    return raw


def write_json(path, data):
    write_bytes(path, encode_json(data))
