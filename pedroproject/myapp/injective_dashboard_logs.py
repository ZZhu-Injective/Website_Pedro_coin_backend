import logging

import requests

logger = logging.getLogger(__name__)

INJECTIVE_LCD = "https://sentry.lcd.injective.network"

# Memo signatures the frontend uses for each feature. We require the tx memo
# to *contain* the signature (allowing future appendices) so the backend can
# attribute the tx to the right feature without trusting the client.
FEATURE_MEMOS = {
    'converter': ['Convert Cw20 or Native token to CW20 or Native token'],
    'airdrop': ['Multisend to different wallets'],
    'launcher': ['Launch token via Pedro Dashboard'],
}


class DashboardLogVerifier:
    """
    Lightweight verification for dashboard tx logs. Confirms:
      - tx exists on Injective and succeeded (code 0)
      - some message in the body is signed by the claimed sender
      - the memo matches the expected signature for the feature
    Stops people from polluting "recent activity" with random hashes.
    """

    @staticmethod
    def verify(tx_hash: str, address: str, feature: str) -> tuple[bool, str]:
        if not tx_hash or not address:
            return False, "Missing tx hash or address"
        memos = FEATURE_MEMOS.get(feature)
        if memos is None:
            return False, f"Unknown feature '{feature}'"

        url = f"{INJECTIVE_LCD}/cosmos/tx/v1beta1/txs/{tx_hash.upper()}"
        try:
            resp = requests.get(url, timeout=10)
        except requests.RequestException as e:
            logger.warning("LCD unreachable while logging %s: %s", tx_hash, e)
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
        memo = body.get("memo", "") or ""
        if not any(sig in memo for sig in memos):
            return False, "Memo does not match this feature"

        for msg in body.get("messages", []):
            sender = msg.get("from_address") or msg.get("sender")
            if sender == address:
                return True, "OK"
            # MsgMultiSend (airdrop) puts the sender(s) under inputs[].address.
            for inp in msg.get("inputs") or []:
                if inp.get("address") == address:
                    return True, "OK"

        return False, "No message in tx is signed by the claimed sender"
