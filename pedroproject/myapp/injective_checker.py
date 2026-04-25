from .models import EligibleAddress


class EligibilityChecker:
    """Check whether a wallet address is in the EligibleAddress table."""

    async def check(self, wallet):
        wallet = (wallet or '').strip()
        if not wallet:
            return {"message": "Sadly, you are not eligible!"}

        is_eligible = await EligibleAddress.objects.filter(address=wallet).aexists()
        if is_eligible:
            return {"message": "Congratulations, You are eligible!"}
        return {"message": "Sadly, you are not eligible!"}


# Backwards-compatible alias so existing imports keep working.
XLSXReader = EligibilityChecker
