from __future__ import annotations

"""
Small Protocol Buffers wire-format codec for Publication messages.

This avoids external build steps while still sending the publisher -> broker payload
as a compact binary message following the .proto schema in proto/publication.proto.
Supported fields:
  1 uint64 publication_id
  2 uint64 created_ns
  3 string company
  4 string city
  5 double value
  6 string category
  7 string source
"""

import struct
from typing import Dict, Tuple

from .models import Publication

WIRE_VARINT = 0
WIRE_FIXED64 = 1
WIRE_LEN = 2


def _encode_varint(value: int) -> bytes:
    if value < 0:
        raise ValueError("varint value must be non-negative")
    out = bytearray()
    while True:
        to_write = value & 0x7F
        value >>= 7
        if value:
            out.append(to_write | 0x80)
        else:
            out.append(to_write)
            break
    return bytes(out)


def _decode_varint(data: bytes, pos: int) -> Tuple[int, int]:
    shift = 0
    result = 0
    while True:
        if pos >= len(data):
            raise ValueError("truncated varint")
        byte = data[pos]
        pos += 1
        result |= (byte & 0x7F) << shift
        if not (byte & 0x80):
            return result, pos
        shift += 7
        if shift > 70:
            raise ValueError("varint too long")


def _tag(field_number: int, wire_type: int) -> bytes:
    return _encode_varint((field_number << 3) | wire_type)


def _string_field(field_number: int, value: str) -> bytes:
    raw = value.encode("utf-8")
    return _tag(field_number, WIRE_LEN) + _encode_varint(len(raw)) + raw


def _uint64_field(field_number: int, value: int) -> bytes:
    return _tag(field_number, WIRE_VARINT) + _encode_varint(value)


def _double_field(field_number: int, value: float) -> bytes:
    return _tag(field_number, WIRE_FIXED64) + struct.pack("<d", value)


def serialize_publication(publication: Publication) -> bytes:
    """Serialize a Publication using protobuf binary wire format."""
    return b"".join(
        [
            _uint64_field(1, publication.publication_id),
            _uint64_field(2, publication.created_ns),
            _string_field(3, publication.company),
            _string_field(4, publication.city),
            _double_field(5, publication.value),
            _string_field(6, publication.category),
            _string_field(7, publication.source),
        ]
    )


def deserialize_publication(data: bytes) -> Publication:
    """Deserialize a Publication from protobuf binary wire format."""
    pos = 0
    fields: Dict[int, object] = {}

    while pos < len(data):
        raw_tag, pos = _decode_varint(data, pos)
        field_number = raw_tag >> 3
        wire_type = raw_tag & 0x07

        if wire_type == WIRE_VARINT:
            value, pos = _decode_varint(data, pos)
            fields[field_number] = value
        elif wire_type == WIRE_FIXED64:
            if pos + 8 > len(data):
                raise ValueError("truncated fixed64 field")
            fields[field_number] = struct.unpack("<d", data[pos : pos + 8])[0]
            pos += 8
        elif wire_type == WIRE_LEN:
            length, pos = _decode_varint(data, pos)
            if pos + length > len(data):
                raise ValueError("truncated length-delimited field")
            fields[field_number] = data[pos : pos + length].decode("utf-8")
            pos += length
        else:
            raise ValueError(f"unsupported wire type: {wire_type}")

    required = [1, 2, 3, 4, 5, 6, 7]
    missing = [field for field in required if field not in fields]
    if missing:
        raise ValueError(f"missing required Publication fields: {missing}")

    return Publication(
        publication_id=int(fields[1]),
        created_ns=int(fields[2]),
        company=str(fields[3]),
        city=str(fields[4]),
        value=float(fields[5]),
        category=str(fields[6]),
        source=str(fields[7]),
    )
