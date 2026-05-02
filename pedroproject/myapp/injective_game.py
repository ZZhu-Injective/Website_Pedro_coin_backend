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
    def verify_pedro_burn(tx_hash: str, expected_from: str) -> tuple[bool, str]:
        if not tx_hash or not expected_from:
            return False, "Missing tx hash or address"

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
                    and coin.get("amount") == ONE_PEDRO_WEI
                ):
                    return True, "OK"

        return False, "No matching 1 $PEDRO burn message in tx"

    @staticmethod
    def verify_captcha(token: str, remote_ip: str = "") -> tuple[bool, str]:
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
        return True, "OK"
