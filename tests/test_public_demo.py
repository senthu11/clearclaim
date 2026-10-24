import os
import unittest
from unittest.mock import patch
from billing import storage


class PublicDemoTests(unittest.TestCase):
    def test_shared_storage_is_blocked_before_access(self):
        with patch.dict(os.environ, {'CLEARCLAIM_PUBLIC_DEMO': '1'}):
            for operation in (lambda: storage.save({}, 'test-password'),
                              storage.list_saved,
                              lambda: storage.load('0' * 32, 'test-password'),
                              lambda: storage.delete('0' * 32)):
                with self.assertRaisesRegex(ValueError, 'disabled'):
                    operation()

    def test_desktop_storage_remains_available(self):
        with patch.dict(os.environ, {'CLEARCLAIM_PUBLIC_DEMO': '0'}):
            storage.require_local_storage()
