import logging
import os

import requests

logger = logging.getLogger(__name__)

PEDRO_DENOM = (
    "factory/inj14ejqjyq8um4p3xfqj74yld5waqljf88f9eneuk/"
    "inj1c6lxety9hqn9q4khwqvjcfa24c2qeqvvfsg4fm"
)
PEDRO_BURN_ADDRESS = "inj1qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqe2hm49"
PEDRO_DECIMALS = 18
ONE_PEDRO_WEI = "1" + "0" * PEDRO_DECIMALS
INJECTIVE_LCD = "https://sentry.lcd.injective.network"
MSG_SEND_TYPE = "/cosmos.bank.v1beta1.MsgSend"
RECAPTCHA_VERIFY_URL = "https://www.google.com/recaptcha/api/siteverify"


class GameVerifier:
    """
    Verifies that a tx hash corresponds to a real on-chain burn of exactly
    1 $PEDRO from `expected_from` to PEDRO_BURN_ADDRESS. Used to gate score
    submissions so the leaderboard can't be spammed for free.
    """

    @staticmethod
    def verify_pedro_burn(
        tx_hash: str,
        expected_from: str,
        expected_amount_pedro: int = 1,
    ) -> tuple[bool, str]:
        """Verifies that `tx_hash` contains a `MsgSend` from `expected_from`
        to the burn address, transferring exactly `expected_amount_pedro`
        whole PEDRO. Defaults to 1 to keep existing call sites working."""
        if not tx_hash or not expected_from:
            return False, "Missing tx hash or address"
        if expected_amount_pedro < 1:
            return False, "Expected burn amount must be >= 1"

        url = f"{INJECTIVE_LCD}/cosmos/tx/v1beta1/txs/{tx_hash.upper()}"
        try:
            resp = requests.get(url, timeout=10)
        except requests.RequestException as e:
            logger.warning("LCD unreachable while verifying %s: %s", tx_hash, e)
            return False, "Could not reach Injective LCD"

        if resp.status_code != 200:
            return False, f"Tx not found (status {resp.status_code})"

        try:
            data = resp.json()
        except ValueError:
            return False, "Invalid JSON from LCD"

        tx_response = data.get("tx_response") or {}
        if tx_response.get("code", -1) != 0:
            return False, "Tx failed on chain"

        expected_wei = str(expected_amount_pedro) + "0" * PEDRO_DECIMALS

        body = (data.get("tx") or {}).get("body") or {}
        for msg in body.get("messages", []):
            if msg.get("@type") != MSG_SEND_TYPE:
                continue
            if msg.get("from_address") != expected_from:
                continue
            if msg.get("to_address") != PEDRO_BURN_ADDRESS:
                continue
            for coin in msg.get("amount", []):
                if (
                    coin.get("denom") == PEDRO_DENOM
                    and coin.get("amount") == expected_wei
                ):
                    return True, "OK"

        return False, f"No matching {expected_amount_pedro} $PEDRO burn message in tx"

    @staticmethod
    def verify_captcha(token: str, remote_ip: str = "") -> tuple[bool, str]:
        """
        reCAPTCHA v3 verification. v3 always returns `success: true` for valid
        tokens — the real signal is the `score` (0.0 = bot, 1.0 = human) and
        `action` matching what the frontend declared.
        """
        secret = os.environ.get("RECAPTCHA_SECRET_KEY", "")
        if not secret:
            # Configuration gap — fail closed so a missing env var on prod is
            # noisy instead of silently allowing unauthenticated submits.
            logger.error("RECAPTCHA_SECRET_KEY not set; rejecting captcha")
            return False, "Captcha not configured on server"
        if not token:
            return False, "Missing captcha token"

        payload = {"secret": secret, "response": token}
        if remote_ip:
            payload["remoteip"] = remote_ip
        try:
            resp = requests.post(RECAPTCHA_VERIFY_URL, data=payload, timeout=5)
        except requests.RequestException as e:
            logger.warning("reCAPTCHA siteverify unreachable: %s", e)
            return False, "Captcha verification unreachable"

        if resp.status_code != 200:
            return False, f"Captcha verification failed (status {resp.status_code})"
        try:
            data = resp.json()
        except ValueError:
            return False, "Invalid JSON from siteverify"
        if not data.get("success"):
            error_codes = data.get("error-codes") or []
            return False, f"Captcha rejected: {','.join(error_codes) or 'unknown'}"

        # v3-specific checks: action and score must look human-ish.
        action = data.get("action")
        if action and action != "submit_score":
            return False, f"Captcha action mismatch (got '{action}')"

        try:
            min_score = float(os.environ.get("RECAPTCHA_MIN_SCORE", "0.5"))
        except ValueError:
            min_score = 0.5
        score = data.get("score")
        if isinstance(score, (int, float)) and score < min_score:
            return False, f"Captcha score too low ({score:.2f} < {min_score:.2f})"

        return True, "OK"
