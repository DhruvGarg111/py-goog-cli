import unittest
from unittest.mock import MagicMock, patch
import sys

# Mock necessary modules
sys.modules['googleapiclient'] = MagicMock()
sys.modules['googleapiclient.discovery'] = MagicMock()
sys.modules['googleapiclient.http'] = MagicMock()
sys.modules['google.oauth2.credentials'] = MagicMock()
sys.modules['google_auth_oauthlib.flow'] = MagicMock()
sys.modules['google.auth.transport.requests'] = MagicMock()
sys.modules['typer'] = MagicMock()
sys.modules['rich'] = MagicMock()
sys.modules['rich.console'] = MagicMock()
sys.modules['rich.table'] = MagicMock()
sys.modules['json5'] = MagicMock()
sys.modules['keyring'] = MagicMock()
sys.modules['keyring.errors'] = MagicMock()
sys.modules['litellm'] = MagicMock()
sys.modules['ddgs'] = MagicMock()
sys.modules['python-dateutil'] = MagicMock()
sys.modules['dateutil'] = MagicMock()
sys.modules['dateutil.parser'] = MagicMock()

from pygog.services.drive import DriveService

class TestDriveSecurity(unittest.TestCase):
    @patch("pygog.services.base.get_config")
    def test_search_files_injection(self, mock_get_config):
        # Mock config
        mock_config = MagicMock()
        mock_config.resolve_account.return_value = "test@example.com"
        mock_config.get_client_for_account.return_value = "test-client"
        mock_get_config.return_value = mock_config

        # Mock Drive API service
        service = DriveService(account="test@example.com")
        mock_drive_service = MagicMock()
        service._service = mock_drive_service

        mock_files = mock_drive_service.files.return_value

        # Malicious query to break out of quotes
        malicious_query = "foo' or name contains 'bar"
        service.search_files(query=malicious_query)

        # Check the 'q' parameter passed to list()
        args, kwargs = mock_files.list.call_args
        q = kwargs.get('q')

        print(f"Generated query: {q}")

        # Verify that single quotes are escaped
        expected_query = "foo\\' or name contains \\'bar"
        self.assertIn(f"'{expected_query}'", q)
        # Verify that it doesn't contain the unescaped malicious query
        self.assertNotIn(f"'{malicious_query}'", q)

    @patch("pygog.services.base.get_config")
    def test_list_files_injection(self, mock_get_config):
        # Mock config
        mock_config = MagicMock()
        mock_config.resolve_account.return_value = "test@example.com"
        mock_config.get_client_for_account.return_value = "test-client"
        mock_get_config.return_value = mock_config

        # Mock Drive API service
        service = DriveService(account="test@example.com")
        mock_drive_service = MagicMock()
        service._service = mock_drive_service

        mock_files = mock_drive_service.files.return_value

        # Malicious parent_id
        malicious_parent = "foo' or 'bar' in parents"
        service.list_files(parent_id=malicious_parent)

        args, kwargs = mock_files.list.call_args
        q = kwargs.get('q')

        print(f"Generated query for list_files: {q}")

        expected_parent = "foo\\' or \\'bar\\' in parents"
        self.assertIn(f"'{expected_parent}'", q)
        self.assertNotIn(f"'{malicious_parent}'", q)

if __name__ == "__main__":
    unittest.main()
