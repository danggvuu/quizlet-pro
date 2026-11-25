import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.request import Request

import server
from scripts import push_sets_to_firebase


class CookieScopeTests(unittest.TestCase):
    def test_only_apex_scoped_quizlet_cookies_are_forwarded(self):
        cookies = [
            SimpleNamespace(name="good", value="1", domain=".Quizlet.com"),
            SimpleNamespace(name="subdomain", value="2", domain="accounts.quizlet.com"),
            SimpleNamespace(name="lookalike", value="3", domain="quizlet.com.evil.test"),
            SimpleNamespace(name="suffix", value="4", domain="notquizlet.com"),
        ]
        self.assertEqual(server.extract_quizlet_cookies(cookies), {"good": "1"})


class FirestorePublisherTests(unittest.TestCase):
    def test_rejects_document_ids_that_can_escape_the_collection_path(self):
        with patch.dict(os.environ, {"FIREBASE_ACCESS_TOKEN": "test-token"}), \
                patch.object(push_sets_to_firebase.urllib.request, "urlopen") as urlopen:
            for doc_id in ["../users/victim", "a/b", "bad?documentId=other", "", True, None]:
                with self.subTest(doc_id=doc_id), self.assertRaises(ValueError):
                    push_sets_to_firebase.upload_set_to_firestore({"id": doc_id})
            urlopen.assert_not_called()

    def test_uses_admin_token_for_firestore_create(self):
        response = Mock()
        response.status = 200
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        with patch.dict(os.environ, {"FIREBASE_ACCESS_TOKEN": "test-token"}), \
                patch.object(push_sets_to_firebase.urllib.request, "urlopen", return_value=response) as urlopen:
            self.assertTrue(push_sets_to_firebase.upload_set_to_firestore({"id": "sample_1"}))
        request = urlopen.call_args.args[0]
        self.assertIsInstance(request, Request)
        self.assertIn("documentId=sample_1", request.full_url)
        self.assertEqual(request.get_header("Authorization"), "Bearer test-token")


if __name__ == "__main__":
    unittest.main()
