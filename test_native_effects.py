"""Offline arithmetic and malformed-frame regressions, with no hardware API."""

import random
import struct
import unittest

from tools.inspect_effect import inspect_frame


def example_frame():
    frame = bytearray(524)
    frame[0] = 0x0B
    struct.pack_into("<BBbbbBH", frame, 2, 3, 0, 16, 0, 0, 0, 100)
    struct.pack_into("<BBbbbBH", frame, 10, 1, 0, -16, 0, 0, 0, 100)
    frame[0x8A] = 255
    frame[0x96] = 2
    struct.pack_into("<H", frame, 0x98, 200)
    return frame


class NativeInspectionTests(unittest.TestCase):
    def test_consistent_synthetic_frame_keeps_hardware_unverified(self):
        report = inspect_frame(example_frame())
        self.assertEqual(report["structural_errors"], [])
        self.assertEqual(report["rate_model_warnings"], [])
        self.assertEqual(report["cycle_drift"], (0, 0, 0))
        self.assertIsNone(report["timing_hypothesis_ms"])
        self.assertFalse(report["hardware_verified"])
        self.assertFalse(report["transmission_available"])
        self.assertNotIn("hypothetical_cycle_seconds", report)
        self.assertEqual(inspect_frame(example_frame(), 10)["hypothetical_cycle_seconds"], 2)

    def test_empty_or_inconsistent_transitions_are_rejected(self):
        for offset, value in (
            (0x96, 0),
            (0x96, 17),
            (0x98, 0),
            (0x99, 1),
            (8, 0),
            (10, 9),
            (0x97, 1),
            (523, 1),
        ):
            frame = example_frame()
            frame[offset] = value
            self.assertTrue(inspect_frame(frame)["structural_errors"], (offset, value))
        frame = example_frame()
        frame[2 + 2 * 8] = 4
        self.assertTrue(inspect_frame(frame)["structural_errors"])

    def test_other_controller_slot_capacity_is_not_assumed_for_klc(self):
        frame = example_frame()
        frame[2] = 17
        report = inspect_frame(frame)
        self.assertEqual(report["structural_errors"], [])
        self.assertGreater(len(report["compatibility_notes"]), 1)
        self.assertFalse(report["hardware_verified"])

    def test_drift_and_clipping_are_reported_as_model_warnings(self):
        frame = example_frame()
        frame[12] = 1
        report = inspect_frame(frame)
        self.assertEqual(report["structural_errors"], [])
        self.assertTrue(report["rate_model_warnings"])
        self.assertNotEqual(report["cycle_drift"], (0, 0, 0))
        struct.pack_into("<H", frame, 0x84, 4080)
        self.assertGreater(len(inspect_frame(frame)["rate_model_warnings"]), 1)

    def test_wave_and_register_constraints(self):
        for offset, value in ((0x90, 2), (0x92, 2), (0x9A, 2)):
            frame = example_frame()
            frame[offset] = value
            self.assertTrue(inspect_frame(frame)["structural_errors"])
        frame = example_frame()
        frame[0x90] = 1
        self.assertTrue(inspect_frame(frame)["structural_errors"])
        struct.pack_into("<H", frame, 0x94, 100)
        self.assertEqual(inspect_frame(frame)["structural_errors"], [])
        struct.pack_into("<H", frame, 0x84, 65535)
        self.assertTrue(inspect_frame(frame)["structural_errors"])

    def test_mutated_inputs_never_enable_transmission_or_raise_parser_errors(self):
        randomizer = random.Random(2740)
        for _ in range(2500):
            frame = bytearray(example_frame())
            for _ in range(randomizer.randrange(1, 10)):
                frame[randomizer.randrange(len(frame))] = randomizer.randrange(256)
            if randomizer.randrange(4) == 0:
                frame = frame[: randomizer.randrange(524)]
            report = inspect_frame(frame)
            self.assertFalse(report["hardware_verified"])
            self.assertFalse(report["transmission_available"])
        self.assertTrue(inspect_frame(bytes(525))["structural_errors"])
        for invalid in (True, 0, 2, "10"):
            with self.assertRaises(ValueError):
                inspect_frame(example_frame(), invalid)
