"""
Platega API Client
"""

import base64
import hashlib
import hmac
import json
import time
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import uuid

from shop.platega.exceptions import PlategaAPIError

__all__ = ["Platega"]


class Platega:
    """
    Main class for interacting with Platega API

    Example:
        client = Platega('merchant_id', 'secret')
        result = client.create_payment(1000, 'RUB', Platega.METHOD_SBP_QR)
    """

    API_URL = "https://app.platega.io"
    VERSION = "1.0.0"

    # Payment methods
    METHOD_SBP_QR = 2  # СБП QR
    METHOD_CARDS_RUB = 10  # Карты (RUB)
    METHOD_CARD_ACQUIRING = 11  # Карточный эквайринг
    METHOD_INTERNATIONAL = 12  # Международный эквайринг
    METHOD_CRYPTO = 13  # Криптовалюта

    # Payment statuses
    STATUS_PENDING = "PENDING"
    STATUS_CONFIRMED = "CONFIRMED"
    STATUS_CANCELED = "CANCELED"
    STATUS_CHARGEBACKED = "CHARGEBACKED"

    def __init__(
        self,
        merchant_id: str,
        secret: str,
        timeout: int = 30,
        payout_secret: str = None,
    ):
        """
        Initialize Platega client

        Args:
            merchant_id: Your Merchant ID (UUID)
            secret: Your API Secret key (X-Secret)
            timeout: Request timeout in seconds
            payout_secret: Separate Payout API secret (PG-HMAC).
                Required only for payouts / saved cards.
        """
        self.merchant_id = merchant_id
        self.secret = secret
        self.timeout = timeout
        self.payout_secret = payout_secret

    # Минимальная и максимальная сумма одного вывода (RUB).
    PAYOUT_MIN_RUB = 1000
    PAYOUT_MAX_RUB = 87500

    def create_payment(
        self,
        amount: float,
        currency: str,
        payment_method: int,
        description: str = None,
        return_url: str = None,
        failed_url: str = None,
        payload: str = None,
        metadata: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Create a new payment

        Args:
            amount: Payment amount
            currency: Currency code (e.g., 'RUB')
            payment_method: Payment method constant (e.g., METHOD_SBP_QR)
            description: Payment description
            return_url: Success redirect URL
            failed_url: Failed redirect URL
            payload: Custom payload data (e.g., order ID)
            metadata: Payer metadata (e.g., {"userId": ...}) for antifraud

        Returns:
            dict: Response data with keys:
                - transactionId (str): Transaction UUID
                - redirect (str): Payment URL
                - status (str): Payment status
                - paymentMethod (str): Payment method name
                - expiresIn (str): Time until expiration

        Raises:
            PlategaAPIError: If API request fails
        """
        data = {
            "paymentMethod": int(payment_method),
            "paymentDetails": {
                "amount": float(amount),
                "currency": str(currency),
            },
        }

        if description:
            data["description"] = str(description)

        if return_url:
            data["return"] = str(return_url)

        if failed_url:
            data["failedUrl"] = str(failed_url)

        if payload:
            data["payload"] = str(payload)

        if metadata:
            data["metadata"] = dict(metadata)

        return self._request("POST", "/transaction/process", data)

    def get_payment_status(self, transaction_id: str) -> Dict[str, Any]:
        """
        Get payment status

        Args:
            transaction_id: Transaction UUID

        Returns:
            dict: Transaction data

        Raises:
            PlategaAPIError: If API request fails
        """
        return self._request("GET", f"/transaction/{transaction_id}")

    def get_rate(
        self,
        payment_method: int,
        currency_from: str,
        currency_to: str,
    ) -> Dict[str, Any]:
        """
        Get exchange rate for payment method

        Args:
            payment_method: Payment method constant
            currency_from: Source currency (e.g., 'RUB')
            currency_to: Target currency (e.g., 'USDT')

        Returns:
            dict: Rate data

        Raises:
            PlategaAPIError: If API request fails
        """
        params = (
            f"merchantId={self.merchant_id}"
            f"&paymentMethod={payment_method}"
            f"&currencyFrom={currency_from}"
            f"&currencyTo={currency_to}"
        )
        return self._request("GET", f"/rates/payment_method_rate?{params}")

    def get_balances(self) -> List[Dict[str, Any]]:
        """
        Get merchant balances (GET /balance/all).

        Returns:
            list: e.g. [{"amount": 15000.5, "currency": "RUB"}, ...]

        Raises:
            PlategaAPIError: If API request fails
        """
        result = self._request("GET", "/balance/all")
        if isinstance(result, list):
            return result

        return []

    def get_saved_cards(self, only_active: bool = True) -> List[Dict]:
        """
        Get saved payout cards (GET /api/v1/cards).

        Only masked data is returned (cardId, masked, last4, brand,
        label, status) — full PAN never leaves Platega.

        Raises:
            PlategaAPIError: If API request fails
            ValueError: If payout secret is not configured
        """
        path = "/api/v1/cards"
        if not only_active:
            path += "?onlyActive=false"

        result = self._signed_request("GET", path)
        if isinstance(result, list):
            return result

        return []

    def create_card_payout(
        self,
        amount_rub: int,
        card_id: str = None,
        card_number: str = None,
    ) -> Dict[str, Any]:
        """
        Create RUB payout to a card (POST /api/v1/payouts/card-rub).

        Args:
            amount_rub: Integer amount in RUB (1000..87500)
            card_id: Saved card ID (alternative to card_number)
            card_number: Full recipient PAN (16 digits)

        Returns:
            dict: withdrawalRecordId, status, cardMasked,
                amountUsdtDebited

        Raises:
            PlategaAPIError: If API request fails
            ValueError: On invalid params or missing payout secret
        """
        try:
            amount_rub = int(amount_rub)
        except (TypeError, ValueError):
            raise ValueError("amount_rub must be an integer")

        if not (self.PAYOUT_MIN_RUB <= amount_rub <= self.PAYOUT_MAX_RUB):
            raise ValueError(
                f"amount_rub must be {self.PAYOUT_MIN_RUB}.."
                f"{self.PAYOUT_MAX_RUB}",
            )

        if bool(card_id) == bool(card_number):
            raise ValueError("Pass either card_id or card_number")

        if card_number is not None:
            card_number = str(card_number).replace(" ", "")
            if not card_number.isdigit() or len(card_number) != 16:
                raise ValueError("card_number must be 16 digits")

        body: Dict[str, Any] = {
            "amountRub": amount_rub,
            "payoutMethod": "CARD",
            "currencyRequested": "RUB",
        }
        if card_id:
            body["cardId"] = str(card_id)
        else:
            body["cardNumber"] = card_number

        return self._signed_request(
            "POST",
            "/api/v1/payouts/card-rub",
            body,
            idempotency_key=str(uuid.uuid4()),
        )

    @staticmethod
    def _payout_signature(
        secret: str,
        method: str,
        path: str,
        timestamp: int,
        idempotency_key: str,
        body_bytes: bytes,
    ) -> str:
        """PG-HMAC signature: Base64(HMAC-SHA256(SECRET, sts))."""
        body_hash = hashlib.sha256(body_bytes or b"").hexdigest()
        string_to_sign = "\n".join(
            [
                method,
                path,
                str(timestamp),
                idempotency_key or "",
                body_hash,
            ],
        )
        digest = hmac.new(
            secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        return base64.b64encode(digest).decode("ascii")

    def _signed_request(
        self,
        method: str,
        path: str,
        body: Optional[Dict] = None,
        idempotency_key: str = "",
    ) -> Any:
        """
        Payout API request signed with the payout secret (PG-HMAC).

        NOTE: query string (if any) is part of the signed path.
        """
        if not self.payout_secret:
            raise ValueError("Payout secret is not configured")

        if body is None:
            body_bytes = b""
        else:
            # Compact separators: signed bytes must equal sent bytes.
            body_bytes = json.dumps(body, separators=(",", ":")).encode(
                "utf-8",
            )

        timestamp = int(time.time())
        signature = self._payout_signature(
            self.payout_secret,
            method,
            path,
            timestamp,
            idempotency_key,
            body_bytes,
        )

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": (
                f"PG-HMAC kid={self.merchant_id}, "
                f"ts={timestamp}, sig={signature}"
            ),
            "User-Agent": f"Platega-Python-SDK/{self.VERSION}",
        }
        if method == "POST":
            headers["Idempotency-Key"] = idempotency_key

        url = f"{self.API_URL}{path}"
        request = Request(
            url,
            data=body_bytes or None,
            headers=headers,
            method=method,
        )

        try:
            with urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as e:
            try:
                error_data = json.loads(e.read().decode("utf-8"))
                message = error_data.get("message", str(e))
            except Exception:
                error_data = {}
                message = str(e)

            raise PlategaAPIError(message, e.code, error_data)
        except URLError as e:
            raise PlategaAPIError(f"Connection error: {e.reason}")
        except json.JSONDecodeError as e:
            raise PlategaAPIError(f"Invalid JSON response: {e}")

    @staticmethod
    def get_payment_methods() -> List[Dict[str, Any]]:
        """
        Get available payment methods

        Returns:
            list: List of payment methods with id, name, and description
        """
        return [
            {
                "id": Platega.METHOD_SBP_QR,
                "name": "СБП QR",
                "description": "СБП с QR-кодом (НСПК / QR)",
            },
            {
                "id": Platega.METHOD_CARDS_RUB,
                "name": "Карты (RUB)",
                "description": "Российские карты (МИР, Visa, Mastercard)",
            },
            {
                "id": Platega.METHOD_CARD_ACQUIRING,
                "name": "Карточный эквайринг",
                "description": "Общий карточный эквайринг",
            },
            {
                "id": Platega.METHOD_INTERNATIONAL,
                "name": "Международный эквайринг",
                "description": "Международные карточные платежи",
            },
            {
                "id": Platega.METHOD_CRYPTO,
                "name": "Криптовалюта",
                "description": "Общие криптовалютные платежи",
            },
        ]

    @staticmethod
    def is_success_status(status: str) -> bool:
        """Check if status indicates successful payment"""
        return status == Platega.STATUS_CONFIRMED

    @staticmethod
    def is_canceled_status(status: str) -> bool:
        """Check if status indicates canceled/failed payment"""
        return status == Platega.STATUS_CANCELED

    @staticmethod
    def is_chargeback_status(status: str) -> bool:
        """Check if status indicates chargeback"""
        return status == Platega.STATUS_CHARGEBACKED

    def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Send API request

        Args:
            method: HTTP method (GET, POST)
            endpoint: API endpoint
            data: Request data

        Returns:
            dict: Response data

        Raises:
            PlategaAPIError: If request fails
        """
        url = f"{self.API_URL}{endpoint}"

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-MerchantId": self.merchant_id,
            "X-Secret": self.secret,
            "User-Agent": f"Platega-Python-SDK/{self.VERSION}",
        }

        body = None
        if data is not None:
            body = json.dumps(data).encode("utf-8")

        request = Request(url, data=body, headers=headers, method=method)

        try:
            with urlopen(request, timeout=self.timeout) as response:
                response_data = json.loads(response.read().decode("utf-8"))
                return response_data

        except HTTPError as e:
            try:
                error_data = json.loads(e.read().decode("utf-8"))
                message = error_data.get("message", str(e))
            except Exception:
                error_data = {}
                message = str(e)

            raise PlategaAPIError(message, e.code, error_data)

        except URLError as e:
            raise PlategaAPIError(f"Connection error: {e.reason}")

        except json.JSONDecodeError as e:
            raise PlategaAPIError(f"Invalid JSON response: {e}")
