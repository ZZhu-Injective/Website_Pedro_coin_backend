from .models import MarketplaceListing


class MarketplaceDataReader:
    async def read_approved_market(self):
        records = []
        idx = 0
        qs = MarketplaceListing.objects.filter(status__iexact='approved')
        async for r in qs:
            idx += 1
            records.append({
                'id': r.legacy_id if r.legacy_id is not None else r.id,
                'WalletAddress': r.wallet_address,
                'title': r.title,
                'description': r.description,
                'category': r.category,
                'price': r.price,
                'skills': r.skills,
                'images': r.images,
                'sellerName': r.seller_name,
                'discordTag': r.discord_tag,
                'createdAt': r.created_at.strftime('%Y-%m-%d %H:%M:%S') if r.created_at else None,
                'Views': r.views,
                'Status': r.status,
                'index': idx,
            })
        return records
