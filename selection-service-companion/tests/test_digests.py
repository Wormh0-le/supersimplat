"""Cross-wire invariants for Companion artifact digests."""

from __future__ import annotations

import unittest

from selection_service_companion.digests import route_b_artifact_digest


class RouteBArtifactDigestTests(unittest.TestCase):
    def test_large_nested_payload_keeps_the_route_b_golden_digest(self) -> None:
        payload = {
            'schemaVersion': 1,
            'target': 'scope',
            'values': [
                {
                    'stableGaussianId': index,
                    'center': [index * 0.125, -0.0, 1.0],
                    'scale': 0.25,
                }
                for index in range(257)
            ],
        }
        self.assertEqual(
            route_b_artifact_digest(payload),
            'sha256:db2db1783aaa2be480b369869eb0deb4006f3c836c99d8127b72fa81bbcc84a7',
        )

    def test_integral_float_and_integer_have_the_same_digest(self) -> None:
        self.assertEqual(
            route_b_artifact_digest({'value': 1.0}),
            route_b_artifact_digest({'value': 1}),
        )

    def test_negative_zero_matches_browser_json_stringify(self) -> None:
        self.assertEqual(
            route_b_artifact_digest({'value': -0.0}),
            route_b_artifact_digest({'value': 0}),
        )

    def test_nested_numbers_are_stable_after_browser_number_normalization(self) -> None:
        original = {
            'cameraToWorld': [1.0, 0.0, 0.5, -0.0],
            'projection': {'width': 640, 'fx': 512.0, 'near': 0.1},
        }
        browser_round_trip = {
            'cameraToWorld': [1, 0, 0.5, 0],
            'projection': {'width': 640, 'fx': 512, 'near': 0.1},
        }
        self.assertEqual(
            route_b_artifact_digest(original),
            route_b_artifact_digest(browser_round_trip),
        )


if __name__ == '__main__':
    unittest.main()
