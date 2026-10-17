import hashlib
import hmac
import time

from fastapi import HTTPException, status


class SePayWebhookVerifier:
    MAX_TIMESTAMP_SKEW_SECONDS = 300

    def __init__(self, secret: str | None) -> None:
        self.secret = (secret or "").strip()

    def verify(
        self,
        *,
        raw_body: bytes,
        signature: str | None,
        timestamp: str | None,
        now_epoch: int | None = None,
    ) -> None:
        if not self.secret:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Payment webhook authentication is not configured.",
            )
        if not signature or not timestamp:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing SePay webhook authentication.",
            )
        try:
            timestamp_value = int(timestamp)
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid SePay webhook timestamp.",
            ) from exc

        current = int(time.time()) if now_epoch is None else now_epoch
        if abs(current - timestamp_value) > self.MAX_TIMESTAMP_SKEW_SECONDS:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="SePay webhook timestamp is outside the allowed window.",
            )

        signed = str(timestamp_value).encode("ascii") + b"." + raw_body
        expected = "sha256=" + hmac.new(
            self.secret.encode("utf-8"), signed, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected, signature.strip()):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid SePay webhook signature.",
            )
