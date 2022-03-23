def test_import_api():
    try:
        from gcp_oauth_clients import (
            GcpConfidentialClient,
            GcpNativeClient,
            GcpOauthClientException,
            TokenResponse,
        )
    except ImportError:
        raise
