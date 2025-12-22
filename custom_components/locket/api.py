"""API client for Locket."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp

from .const import FIREBASE_BASE_URL, LOCKET_BASE_URL, FIREBASE_API_KEY

_LOGGER = logging.getLogger(__name__)


class LocketAPIError(Exception):
    """Exception raised for Locket API errors."""

    def __init__(self, message: str, code: int | None = None) -> None:
        """Initialize error."""
        self.message = message
        self.code = code
        super().__init__(self.message)


class LocketAPI:
    """API client for Locket."""

    def __init__(
        self,
        token: str | None = None,
        firebase_api_key: str = FIREBASE_API_KEY,
    ) -> None:
        """Initialize the API client."""
        self._token = token
        self._firebase_api_key = firebase_api_key
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        """Close the session."""
        if self._session and not self._session.closed:
            await self._session.close()

    def set_token(self, token: str) -> None:
        """Set the authentication token."""
        self._token = token

    def get_token(self) -> str | None:
        """Get the current authentication token."""
        return self._token

    async def _fetch_firebase(
        self,
        endpoint: str,
        method: str = "POST",
        body: dict[str, Any] | None = None,
        token: str | None = None,
    ) -> dict[str, Any]:
        """Make a request to Firebase API."""
        session = await self._get_session()
        url = f"{endpoint}?key={self._firebase_api_key}"

        headers = {
            "Content-Type": "application/json",
            "Accept-Language": "en-US",
            "User-Agent": "FirebaseAuth.iOS/10.23.1 com.locket.Locket/1.82.0 iPhone/18.0 hw/iPhone12_1",
            "X-Ios-Bundle-Identifier": "com.locket.Locket",
            "X-Client-Version": "iOS/FirebaseSDK/10.23.1/FirebaseCore-iOS",
            "X-Firebase-GMPID": "1:641029076083:ios:cc8eb46290d69b234fa606",
            "X-Firebase-Client": "H4sIAAAAAAAAAKtWykhNLCpJSk0sKVayio7VUSpLLSrOzM9TslIyUqoFAFyivEQfAAAA",
            "X-Firebase-AppCheck": "eyJraWQiOiJNbjVDS1EiLCJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJzdWIiOiIxOjY0MTAyOTA3NjA4Mzppb3M6Y2M4ZWI0NjI5MGQ2OWIyMzRmYTYwNiIsImF1ZCI6WyJwcm9qZWN0c1wvNjQxMDI5MDc2MDgzIiwicHJvamVjdHNcL2xvY2tldC00MjUyYSJdLCJwcm92aWRlciI6ImRldmljZV9jaGVja19kZXZpY2VfaWRlbnRpZmljYXRpb24iLCJpc3MiOiJodHRwczpcL1wvZmlyZWJhc2VhcHBjaGVjay5nb29nbGVhcGlzLmNvbVwvNjQxMDI5MDc2MDgzIiwiZXhwIjoxNzIyMTY3ODk4LCJpYXQiOjE3MjIxNjQyOTgsImp0aSI6ImlHUGlsT1dDZGg4Mll3UTJXRC1neEpXeWY5TU9RRFhHcU5OR3AzTjFmRGcifQ.lqTOJfdoYLpZwYeeXtRliCdkVT7HMd7_Lj-d44BNTGuxSYPIa9yVAR4upu3vbZSh9mVHYS8kJGYtMqjP-L6YXsk_qsV_gzKC2IhVAV6KbPDRHdevMfBC6fRiOSVn7vt749GVFdZqAuDCXhCILsaMhvgDBgZoDilgAPtpNwyjz-VtRB7OdOUbuKTCqdoSOX0SJWVUMyuI8nH0-unY--YRctunK8JHZDxBaM_ahVggYPWBCpzxq9Yeq8VSPhadG_tGNaADStYPaeeUkZ7DajwWqH5ze6ESpuFNgAigwPxCM735_ZiPeD7zHYwppQA9uqTWszK9v9OvWtFCsgCEe22O8awbNbuEBTKJpDQ8xvZe8iEYyhfUPncER3S-b1CmuXR7tFCdTgQe5j7NGWjFvN_CnL7D2nudLwxWlpqwASCHvHyi8HBaJ5GpgriTLXAAinY48RukRDBi9HwEzpRecELX05KTD2TTOfQCjKyGpfG2VUHP5Xm36YbA3iqTDoDXWMvV",
        }

        if token:
            headers["Authorization"] = f"Bearer {token}"

        try:
            async with session.request(
                method, url, headers=headers, json=body
            ) as response:
                if response.status != 200:
                    error_data = await response.json()
                    error_msg = error_data.get("error", {}).get("message", "Firebase API error")
                    error_code = error_data.get("error", {}).get("code")
                    raise LocketAPIError(error_msg, error_code)

                return await response.json()
        except aiohttp.ClientError as err:
            raise LocketAPIError(f"Network error: {str(err)}") from err

    async def _fetch_locket(
        self,
        endpoint: str,
        method: str = "POST",
        body: dict[str, Any] | None = None,
        token: str | None = None,
    ) -> dict[str, Any]:
        """Make a request to Locket API."""
        session = await self._get_session()
        url = f"{LOCKET_BASE_URL}/{endpoint}"

        headers = {"Content-Type": "application/json"}

        auth_token = token or self._token
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"

        try:
            async with session.request(
                method, url, headers=headers, json=body
            ) as response:
                if response.status != 200:
                    error_data = await response.json()
                    error_msg = error_data.get("message", f"Locket API error: {response.status}")
                    raise LocketAPIError(error_msg, response.status)

                result = await response.json()
                return result.get("result", result)
        except aiohttp.ClientError as err:
            raise LocketAPIError(f"Network error: {str(err)}") from err

    async def login(self, email: str, password: str) -> dict[str, Any]:
        """Login with email and password."""
        return await self._fetch_firebase(
            f"{FIREBASE_BASE_URL}/verifyPassword",
            method="POST",
            body={
                "email": email,
                "password": password,
                "returnSecureToken": True,
                "clientType": "CLIENT_TYPE_IOS",
            },
        )

    async def refresh_token(self, refresh_token: str) -> dict[str, Any]:
        """Refresh the authentication token."""
        return await self._fetch_firebase(
            "https://securetoken.googleapis.com/v1/token",
            method="POST",
            body={
                "grantType": "refresh_token",
                "refreshToken": refresh_token,
            },
        )

    async def request_phone_otp(self, phone_e164: str) -> dict[str, Any]:
        """Request OTP code for phone authentication."""
        return await self._fetch_locket(
            "sendVerificationCode",
            method="POST",
            body={
                "data": {
                    "deviceModel": "iPhone12,1",
                    "operation": "hybrid",
                    "phone": phone_e164,
                    "use_password_if_available": False,
                }
            },
        )

    async def verify_phone_otp(
        self, phone_e164: str, code: str
    ) -> dict[str, Any]:
        """Verify OTP code and get custom token."""
        return await self._fetch_locket(
            "checkVerificationCode",
            method="POST",
            body={
                "data": {
                    "phone": phone_e164,
                    "verification_code": code,
                }
            },
        )

    async def exchange_otp_token_for_id_token(
        self, custom_token: str
    ) -> dict[str, Any]:
        """Exchange custom token for ID token."""
        return await self._fetch_firebase(
            f"{FIREBASE_BASE_URL}/verifyCustomToken",
            method="POST",
            body={
                "returnSecureToken": True,
                "token": custom_token,
            },
        )

    async def fetch_latest_moment(self, token: str | None = None) -> dict[str, Any]:
        """Fetch the latest moment."""
        return await self._fetch_locket(
            "getLatestMomentV2",
            method="POST",
            body={
                "data": {
                    "last_fetch": 1,
                    "should_count_missed_moments": True,
                }
            },
            token=token or self._token,
        )

