from .models import Talent


class TalentDatabase:
    def get_talent_by_wallet(self, wallet_address: str) -> dict:
        try:
            qs = Talent.objects.filter(wallet_address__iexact=wallet_address)
            submissions = [t.to_excel_dict() for t in qs]

            if not submissions:
                return {
                    "info": "no",
                    "message": "No submissions found for this wallet address",
                }

            if len(submissions) == 1:
                return {
                    "info": "yes",
                    "message": "Single submission found",
                    **submissions[0],
                }

            return {
                "info": "yes",
                "message": f"{len(submissions)} submissions found",
                "count": len(submissions),
                "wallet_address": wallet_address,
                "submissions": submissions,
            }

        except Exception as e:
            print(f"Error in get_talent_by_wallet: {e}")
            return {
                "info": "no",
                "message": f"Error processing request: {e}",
            }
