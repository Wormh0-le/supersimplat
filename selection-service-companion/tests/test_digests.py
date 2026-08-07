"""Cross-wire invariants for Companion artifact digests."""

from __future__ import annotations

import unittest

from selection_service_companion.digests import route_b_artifact_digest


class RouteBArtifactDigestTests(unittest.TestCase):
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
