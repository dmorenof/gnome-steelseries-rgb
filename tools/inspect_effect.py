#!/usr/bin/env python3
"""Inspect one captured 524-byte effect frame offline, without a replay interface.

The byte layout comes from public community protocol notes. Timing and signed
rate interpretation remain hypotheses until validated on the target KLC.
"""

import argparse
import json
import struct
from pathlib import Path

FRAME_SIZE = 524
TRANSITION_LIMIT = 16
REGISTER_LIMIT = 4080


def inspect_frame(frame, tick_ms=None):
    if tick_ms not in (None, 1, 10) or isinstance(tick_ms, bool):
        raise ValueError("The supported timing hypotheses are 1 ms and 10 ms.")
    errors = []
    warnings = []
    compatibility = [
        "KLC timing, slot capacity and wave geometry require target-specific verification."
    ]
    report = {
        "frame_bytes": len(frame),
        "structural_errors": errors,
        "rate_model_warnings": warnings,
        "compatibility_notes": compatibility,
        "hardware_verified": False,
        "transmission_available": False,
        "timing_hypothesis_ms": tick_ms,
    }
    if len(frame) != FRAME_SIZE:
        errors.append("Expected exactly 524 payload bytes without a HID report-ID prefix.")
        return report
    if frame[:2] != bytes((0x0B, 0)):
        errors.append("Expected the native-effect opcode and reserved zero byte.")
        return report
    count = frame[0x96]
    total = struct.unpack_from("<H", frame, 0x98)[0]
    slot = frame[2]
    if not 1 <= count <= TRANSITION_LIMIT:
        errors.append("Transition count must be between 1 and 16.")
    if total == 0:
        errors.append("Total duration is zero.")
    if slot > 15:
        compatibility.append(
            "The slot identifier exceeds the 0..15 range reported for the other-model ALC."
        )
    if frame[0x82:0x84] != bytes(2) or frame[0x8A:0x8C] != bytes((255, 0)):
        errors.append("Reserved bytes or the color separator differ from the reviewed layout.")
    if frame[0x97] != 0 or any(frame[0x9B:]):
        errors.append("Unrecognized reserved or trailing data.")
    start = struct.unpack_from("<3H", frame, 0x84)
    if any(value > REGISTER_LIMIT for value in start):
        errors.append("The starting color exceeds the reviewed register range.")
    origin_x, origin_y, axis_x, axis_y, wavelength = struct.unpack_from("<5H", frame, 0x8C)
    direction = frame[0x9A]
    if axis_x not in (0, 1) or axis_y not in (0, 1) or direction not in (0, 1):
        errors.append("Unknown wave-axis or direction flags.")
    if (axis_x or axis_y) and wavelength == 0:
        errors.append("A wave axis is enabled with a zero wavelength.")
    transitions = []
    state = list(start)
    duration_sum = 0
    for index in range(min(count, TRANSITION_LIMIT)):
        offset = 2 + index * 8
        expected_index = slot if index == 0 else index
        if frame[offset] != expected_index or frame[offset + 1] or frame[offset + 5]:
            errors.append(f"Transition {index} has an unexpected index or reserved byte.")
        rates = struct.unpack_from("<3b", frame, offset + 2)
        duration = struct.unpack_from("<H", frame, offset + 6)[0]
        if duration == 0:
            errors.append(f"Transition {index} has zero duration.")
        duration_sum += duration
        state = [value + rate * duration for value, rate in zip(state, rates)]
        if any(not 0 <= value <= REGISTER_LIMIT for value in state):
            warnings.append(
                f"Transition {index} leaves the register range under the rate hypothesis."
            )
        transitions.append({"index": index, "rates": rates, "duration_units": duration})
    if duration_sum != total:
        errors.append("Transition durations do not sum to the declared total.")
    if count <= TRANSITION_LIMIT and any(frame[2 + count * 8 : 0x82]):
        errors.append("Unused transition storage contains nonzero data.")
    drift = tuple(final - initial for initial, final in zip(start, state))
    if any(drift):
        warnings.append("The rate hypothesis predicts a nonzero color change per cycle.")
    report.update(
        slot=slot,
        transition_count=count,
        total_duration_units=total,
        duration_sum=duration_sum,
        starting_registers=start,
        cycle_drift=drift,
        wave={
            "origin": (origin_x, origin_y),
            "axes": (axis_x, axis_y),
            "wavelength": wavelength,
            "direction_flag": direction,
        },
        transitions=transitions,
    )
    if tick_ms is not None:
        report["hypothetical_cycle_seconds"] = total * tick_ms / 1000
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "frame", type=Path, help="One binary payload, or hexadecimal text with --hex."
    )
    parser.add_argument(
        "--hex", action="store_true", help="Read hexadecimal text instead of binary."
    )
    parser.add_argument(
        "--tick-ms",
        type=int,
        choices=(1, 10),
        help="Explicit timing hypothesis, without hardware verification.",
    )
    args = parser.parse_args()
    try:
        with args.frame.open("rb") as stream:
            raw = stream.read(4097 if args.hex else 525)
        if args.hex:
            if len(raw) > 4096:
                raise ValueError("Hexadecimal input exceeds 4096 bytes.")
            raw = bytes.fromhex(raw.decode("ascii"))
        report = inspect_frame(raw, args.tick_ms)
        print(json.dumps(report, indent=2))
    except (OSError, ValueError) as error:
        parser.exit(2, str(error) + "\n")
    return 2 if report["structural_errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
