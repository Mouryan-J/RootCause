import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from unittest.mock import patch

from rootcause.core.security import require_api_key


@pytest.mark.asyncio
async def test_auth_disabled_when_no_key_set():
    with patch("rootcause.core.security.get_settings") as mock:
        mock.return_value.api_secret_key = ""
        # Should not raise when api_secret_key is empty
        await require_api_key(credentials=None)


@pytest.mark.asyncio
async def test_auth_rejects_wrong_key():
    with patch("rootcause.core.security.get_settings") as mock:
        mock.return_value.api_secret_key = "correct-key"
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="wrong-key")
        with pytest.raises(HTTPException) as exc_info:
            await require_api_key(credentials=creds)
        assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_auth_accepts_correct_key():
    with patch("rootcause.core.security.get_settings") as mock:
        mock.return_value.api_secret_key = "correct-key"
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="correct-key")
        await require_api_key(credentials=creds)


@pytest.mark.asyncio
async def test_auth_rejects_missing_credentials_when_key_required():
    with patch("rootcause.core.security.get_settings") as mock:
        mock.return_value.api_secret_key = "required-key"
        with pytest.raises(HTTPException) as exc_info:
            await require_api_key(credentials=None)
        assert exc_info.value.status_code == 401
