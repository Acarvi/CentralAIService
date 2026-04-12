import pytest
import sys
import os
from unittest.mock import patch, MagicMock

# Add SentinelAPI to path
SENTINEL_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "SentinelAPI"))
if SENTINEL_PATH not in sys.path:
    sys.path.insert(0, SENTINEL_PATH)

def test_sentinel_blocks_startup_on_api_failure():
    """Verify that if validate_all_apis returns False, the system exits."""
    with patch("api_checker.validate_all_apis") as mock_val:
        mock_val.return_value = False
        
        # We need to mock sys.exit to prevent the test runner from exiting
        with patch("sys.exit") as mock_exit:
            # We also need to mock bootstrap.validate_environment to avoid scanning the whole disk
            with patch("security_audit.validate_environment"):
                import bootstrap
                bootstrap.activate_security()
                
                mock_exit.assert_called_with(1)

def test_sentinel_allows_startup_on_success():
    """Verify that if validate_all_apis returns True, the system proceeds."""
    with patch("api_checker.validate_all_apis") as mock_val:
        mock_val.return_value = True
        
        with patch("sys.exit") as mock_exit:
            with patch("security_audit.validate_environment"):
                with patch("log_sanitizer.init_sanitizer"):
                    import bootstrap
                    bootstrap.activate_security()
                    
                    mock_exit.assert_not_called()
