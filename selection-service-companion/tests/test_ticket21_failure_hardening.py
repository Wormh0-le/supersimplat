from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
import unittest
from urllib.request import Request, urlopen

from selection_service_companion.masking import MaskSessionError
from selection_service_companion.server import create_server
from selection_service_companion.state import CompanionState


class AsyncArtifactAttemptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = TemporaryDirectory()
        self.state = CompanionState(Path(self.temporary_directory.name))
        self.server = create_server(
            state=self.state,
            endpoint="http://127.0.0.1:0",
            profile="loopback",
            allowed_origins=["https://editor.example"],
        )
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.endpoint = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temporary_directory.cleanup()

    def dispose_target(self, target_context_id: str) -> None:
        with urlopen(
            Request(
                f"{self.endpoint}/ai-select/targets/{target_context_id}",
                method="DELETE",
                headers={"Origin": "https://editor.example"},
            )
        ) as response:
            self.assertEqual(response.status, 204)

    def test_same_attempt_replays_and_a_new_intent_gets_distinct_admission(self) -> None:
        request = {"evidenceAttemptId": "evidence-1", "identity": "exact"}
        key, admission, owns = self.state._admit_async_artifact(
            request,
            self.state._direct_evidence_admissions,
            "direct-evidence:evidence-1",
        )
        self.assertTrue(owns)
        duplicate_key, duplicate, duplicate_owns = self.state._admit_async_artifact(
            request,
            self.state._direct_evidence_admissions,
            "direct-evidence:evidence-1",
        )
        self.assertEqual(duplicate_key, key)
        self.assertIs(duplicate, admission)
        self.assertFalse(duplicate_owns)
        with self.assertRaises(MaskSessionError) as conflict:
            self.state._admit_async_artifact(
                {**request, "identity": "different"},
                self.state._direct_evidence_admissions,
                "direct-evidence:evidence-1",
            )
        self.assertEqual(conflict.exception.code, "attemptIdentityConflict")

        response = {
            "status": "complete",
            "evidenceAttemptId": "evidence-1",
            "artifact": {"complete": True},
        }
        self.state._complete_async_artifact(
            key=key,
            admission=admission,
            admissions=self.state._direct_evidence_admissions,
            operation_id="direct-evidence:evidence-1",
            response=response,
        )
        replay = self.state._replay_async_artifact(
            duplicate,
            failure_code="directEvidenceFailure",
            failure_message="lost",
        )
        self.assertEqual(replay, response)

        distinct = {**request, "evidenceAttemptId": "evidence-2"}
        _, next_admission, next_owns = self.state._admit_async_artifact(
            distinct,
            self.state._direct_evidence_admissions,
            "direct-evidence:evidence-2",
        )
        self.assertTrue(next_owns)
        self.assertIsNot(next_admission, admission)
        self.assertEqual(
            self.state._replay_async_artifact(
                admission,
                failure_code="directEvidenceFailure",
                failure_message="lost",
            ),
            response,
        )

    def test_target_disposal_clears_admissions_and_rejects_late_completion(self) -> None:
        request = {
            "promptSynthesisAttemptId": "prompt-1",
            "identity": "exact",
            "requestBinding": {"targetContextId": "target-a"},
        }
        key, admission, owns = self.state._admit_async_artifact(
            request,
            self.state._generated_view_prompt_admissions,
            "prompt-synthesis:prompt-1",
        )
        self.assertTrue(owns)

        self.dispose_target("target-a")
        self.assertEqual(self.state._generated_view_prompt_admissions, {})
        self.state._complete_async_artifact(
            key=key,
            admission=admission,
            admissions=self.state._generated_view_prompt_admissions,
            operation_id="prompt-synthesis:prompt-1",
            response={"status": "ready"},
        )

        self.assertIsNone(self.state._active_evidence_operation)
        self.assertIsNone(admission.publication)
        with self.assertRaises(MaskSessionError) as stale:
            self.state._replay_async_artifact(
                admission,
                failure_code="promptSynthesisFailure",
                failure_message="lost",
            )
        self.assertEqual(stale.exception.code, "staleAttempt")

    def test_delayed_target_a_cleanup_cannot_erase_target_b_admission(self) -> None:
        request_a = {
            "evidenceAttemptId": "evidence-a",
            "requestBinding": {"targetContextId": "target-a"},
        }
        key_a, admission_a, _ = self.state._admit_async_artifact(
            request_a,
            self.state._direct_evidence_admissions,
            "direct-evidence:evidence-a",
        )
        self.state._complete_async_artifact(
            key=key_a,
            admission=admission_a,
            admissions=self.state._direct_evidence_admissions,
            operation_id="direct-evidence:evidence-a",
            response={"status": "complete"},
        )
        request_b = {
            "evidenceAttemptId": "evidence-b",
            "requestBinding": {"targetContextId": "target-b"},
        }
        key_b, admission_b, owns_b = self.state._admit_async_artifact(
            request_b,
            self.state._direct_evidence_admissions,
            "direct-evidence:evidence-b",
        )
        self.assertTrue(owns_b)

        self.dispose_target("target-a")

        self.assertIs(
            self.state._direct_evidence_admissions.get(key_b),
            admission_b,
        )
        self.assertEqual(
            self.state._active_evidence_operation,
            "direct-evidence:evidence-b",
        )

    def test_oom_failure_replays_without_any_partial_publication(self) -> None:
        request = {"liftAttemptId": "lift-1", "identity": "exact"}
        key, admission, owns = self.state._admit_async_artifact(
            request,
            self.state._candidate_re_lift_admissions,
            "candidate-re-lift:lift-1",
        )
        self.assertTrue(owns)
        failure = MaskSessionError(
            "outOfMemory",
            "Injected locked-GPU OOM before Candidate publication.",
        )
        self.state._complete_async_artifact(
            key=key,
            admission=admission,
            admissions=self.state._candidate_re_lift_admissions,
            operation_id="candidate-re-lift:lift-1",
            failure=failure,
        )

        self.assertIsNone(admission.publication)
        with self.assertRaises(MaskSessionError) as replayed:
            self.state._replay_async_artifact(
                admission,
                failure_code="candidateReLiftFailure",
                failure_message="lost",
            )
        self.assertEqual(replayed.exception.code, "outOfMemory")

    def test_completed_attempt_replay_is_bounded_and_survives_later_attempts(self) -> None:
        for index in range(70):
            attempt = f"evidence-{index}"
            request = {"evidenceAttemptId": attempt, "identity": "exact"}
            key, admission, owns = self.state._admit_async_artifact(
                request,
                self.state._direct_evidence_admissions,
                f"direct-evidence:{attempt}",
            )
            self.assertTrue(owns)
            self.state._complete_async_artifact(
                key=key,
                admission=admission,
                admissions=self.state._direct_evidence_admissions,
                operation_id=f"direct-evidence:{attempt}",
                response={"status": "complete", "attempt": attempt},
            )

        self.assertEqual(len(self.state._direct_evidence_admissions), 64)
        retained_request = {
            "evidenceAttemptId": "evidence-6",
            "identity": "exact",
        }
        _, retained, owns = self.state._admit_async_artifact(
            retained_request,
            self.state._direct_evidence_admissions,
            "direct-evidence:evidence-6",
        )
        self.assertFalse(owns)
        self.assertEqual(
            self.state._replay_async_artifact(
                retained,
                failure_code="directEvidenceFailure",
                failure_message="lost",
            ),
            {"status": "complete", "attempt": "evidence-6"},
        )


if __name__ == "__main__":
    unittest.main()
