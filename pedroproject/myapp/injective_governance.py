import logging

import requests

logger = logging.getLogger(__name__)

INJECTIVE_LCD = "https://sentry.lcd.injective.network"
MSG_SEND_TYPE = "/cosmos.bank.v1beta1.MsgSend"
VOTE_MEMO_PREFIX = "pedro-vote"
VALID_CHOICES = {"liquidity", "buy_nfts", "giveaway"}


def expected_memo(month: str, choice: str) -> str:
    return f"{VOTE_MEMO_PREFIX}:{month}:{choice}"


class GovernanceVerifier:
    """
    Verifies that a tx hash represents a genuine vote: a `MsgSend` signed by
    `expected_from` (sent to themselves to keep gas trivial) carrying the
    expected vote memo. The transfer amount is irrelevant — the tx is a
    signed receipt for the vote, not a payment.
    """

    @staticmethod
    def verify_vote(tx_hash: str, expected_from: str, month: str, choice: str) -> tuple[bool, str]:
        if not tx_hash or not expected_from:
            return False, "Missing tx hash or address"
        if choice not in VALID_CHOICES:
            return False, f"Invalid choice (allowed: {sorted(VALID_CHOICES)})"

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
        memo = body.get("memo", "")
        if memo != expected_memo(month, choice):
            return False, (
                f"Memo mismatch (expected '{expected_memo(month, choice)}', "
                f"got '{memo}')"
            )

        # At least one MsgSend from the claimed voter must exist. Self-send
        # is the recommended pattern but we don't enforce destination — the
        # signer is what matters.
        for msg in body.get("messages", []):
            if msg.get("@type") != MSG_SEND_TYPE:
                continue
            if msg.get("from_address") == expected_from:
                return True, "OK"

        return False, "No MsgSend from the claimed voter in this tx"
