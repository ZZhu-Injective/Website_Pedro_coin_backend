from django.db import models


class GameLeaderboardEntry(models.Model):
    address = models.CharField(max_length=64, db_index=True)
    name = models.CharField(max_length=64)
    score = models.BigIntegerField()
    tx_hash = models.CharField(max_length=128, unique=True, db_index=True)
    month = models.CharField(max_length=7, db_index=True)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-score', 'submitted_at']

    def __str__(self):
        return f"{self.name} - {self.score} ({self.month})"


class GameUpgradeState(models.Model):
    address = models.CharField(max_length=64, unique=True, db_index=True)
    click_level = models.IntegerField(default=0)
    auto_level = models.IntegerField(default=0)
    steal_level = models.IntegerField(default=0)
    score = models.BigIntegerField(default=0)
    last_steal_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.address} (click={self.click_level}, auto={self.auto_level}, steal={self.steal_level})"


class RaffleTicket(models.Model):
    """One row per ticket entered in a given week. Free tickets come from
    NFT holdings, paid tickets come from a $PEDRO burn."""
    SOURCE_FREE = 'free'
    SOURCE_PAID = 'paid'
    SOURCE_CHOICES = [
        (SOURCE_FREE, 'Free (NFT holder)'),
        (SOURCE_PAID, 'Paid'),
    ]

    week = models.CharField(max_length=10, db_index=True)
    address = models.CharField(max_length=64, db_index=True)
    source = models.CharField(max_length=16, choices=SOURCE_CHOICES)
    # Multiple paid tickets share the same tx_hash when bought together,
    # so this is indexed but NOT unique. Replay protection lives in
    # `RafflePurchase.tx_hash` (which IS unique).
    tx_hash = models.CharField(max_length=128, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['week', 'address'])]

    def __str__(self):
        return f"#{self.id} {self.week} {self.address} ({self.source})"


class RaffleFreeClaim(models.Model):
    """Records that an NFT holder has used their free ticket allowance for a
    given week. Enforced by `unique_together` so each wallet can claim at
    most once per week."""
    address = models.CharField(max_length=64, db_index=True)
    week = models.CharField(max_length=10, db_index=True)
    nft_count_at_claim = models.IntegerField()
    tickets_granted = models.IntegerField()
    claimed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('address', 'week')]
        ordering = ['-claimed_at']

    def __str__(self):
        return f"{self.week} {self.address} +{self.tickets_granted} (free)"


class RafflePurchase(models.Model):
    """One row per paid ticket purchase tx — used purely to prevent the
    same on-chain burn from being re-credited."""
    tx_hash = models.CharField(max_length=128, unique=True, db_index=True)
    address = models.CharField(max_length=64, db_index=True)
    week = models.CharField(max_length=10, db_index=True)
    tickets = models.IntegerField()
    pedro_burned = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.week} {self.address} +{self.tickets} for {self.pedro_burned} PEDRO"


class RaffleResult(models.Model):
    """One row per completed week's draw. Winner opens a Discord ticket to
    claim 1 INJ; `payout_tx_hash` is filled by the team after payout."""
    week = models.CharField(max_length=10, unique=True, db_index=True)
    winning_address = models.CharField(max_length=64, db_index=True)
    winning_ticket_id = models.BigIntegerField()
    winning_name = models.CharField(max_length=64, blank=True)
    ticket_count = models.IntegerField()
    picked_at = models.DateTimeField(auto_now_add=True)
    payout_tx_hash = models.CharField(max_length=128, blank=True)

    class Meta:
        ordering = ['-week']

    def __str__(self):
        return f"{self.week} -> {self.winning_address} (#{self.winning_ticket_id})"


class GameStealLog(models.Model):
    """One row per successful steal — keeps a simple audit trail and lets the
    UI show recent activity if we ever want to."""
    attacker = models.CharField(max_length=64, db_index=True)
    target = models.CharField(max_length=64, db_index=True)
    amount = models.BigIntegerField()
    attacker_level = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.attacker} -> {self.target} ({self.amount})"


class GovernanceVoterSnapshot(models.Model):
    month = models.CharField(max_length=7, db_index=True)
    address = models.CharField(max_length=64, db_index=True)
    nft_count = models.IntegerField()
    captured_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('month', 'address')]
        ordering = ['-month', '-nft_count']

    def __str__(self):
        return f"{self.month} {self.address} ({self.nft_count})"


class GovernanceVote(models.Model):
    address = models.CharField(max_length=64, db_index=True)
    month = models.CharField(max_length=7, db_index=True)
    choice = models.CharField(max_length=32, db_index=True)
    points = models.IntegerField()
    tx_hash = models.CharField(max_length=128, unique=True, db_index=True)
    voted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('address', 'month')]
        ordering = ['-voted_at']

    def __str__(self):
        return f"{self.month} {self.address} -> {self.choice} ({self.points})"


class DashboardTxLog(models.Model):
    FEATURE_CONVERTER = 'converter'
    FEATURE_AIRDROP = 'airdrop'
    FEATURE_LAUNCHER = 'launcher'
    FEATURE_CHOICES = [
        (FEATURE_CONVERTER, 'Converter'),
        (FEATURE_AIRDROP, 'Airdrop'),
        (FEATURE_LAUNCHER, 'Launcher'),
    ]

    tx_hash = models.CharField(max_length=128, unique=True, db_index=True)
    feature = models.CharField(max_length=32, db_index=True, choices=FEATURE_CHOICES)
    address = models.CharField(max_length=64, db_index=True)
    summary = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.feature} {self.address} {self.tx_hash[:12]}"


class GovernanceMonthResult(models.Model):
    month = models.CharField(max_length=7, unique=True, db_index=True)
    winning_choice = models.CharField(max_length=32, blank=True)
    points_liquidity = models.IntegerField(default=0)
    points_buy_nfts = models.IntegerField(default=0)
    points_giveaway = models.IntegerField(default=0)
    payout_tx_hash = models.CharField(max_length=128, blank=True)
    payout_amount = models.CharField(max_length=64, blank=True)
    notes = models.TextField(blank=True)
    finalized_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-month']

    def __str__(self):
        return f"{self.month} -> {self.winning_choice}"


class TokenHolder(models.Model):
    address = models.CharField(max_length=255, unique=True)
    native_value = models.FloatField(default=0)
    cw20_value = models.FloatField(default=0)
    total_value = models.FloatField(default=0)
    percentage = models.FloatField(default=0)

    def __str__(self):
        return self.address


class EligibleAddress(models.Model):
    address = models.CharField(max_length=64, unique=True, db_index=True)
    note = models.CharField(max_length=255, blank=True)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-added_at']

    def __str__(self):
        return self.address


class VerifiedToken(models.Model):
    denom = models.CharField(max_length=255, unique=True, db_index=True)
    address = models.CharField(max_length=255, blank=True)
    is_native = models.BooleanField(default=False)
    token_verification = models.CharField(max_length=64, blank=True)
    name = models.CharField(max_length=255, blank=True)
    decimals = models.IntegerField(default=18)
    symbol = models.CharField(max_length=64, blank=True, db_index=True)
    override_symbol = models.CharField(max_length=64, blank=True, db_index=True)
    logo = models.URLField(max_length=500, blank=True)
    coin_gecko_id = models.CharField(max_length=128, blank=True)
    token_type = models.CharField(max_length=64, blank=True)
    external_logo = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return self.symbol or self.denom


class ScamWallet(models.Model):
    address = models.CharField(max_length=64, unique=True, db_index=True)
    note = models.CharField(max_length=255, blank=True)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-added_at']

    def __str__(self):
        return self.address


class ScamReport(models.Model):
    address = models.CharField(max_length=255, blank=True, db_index=True)
    time = models.CharField(max_length=64, blank=True)
    project = models.CharField(max_length=255, blank=True)
    amount = models.CharField(max_length=128, blank=True)
    info = models.TextField(blank=True)
    group = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ['-id']

    def __str__(self):
        return f"{self.project} ({self.address})"


class MarketplaceListing(models.Model):
    legacy_id = models.IntegerField(null=True, blank=True, db_index=True)
    wallet_address = models.CharField(max_length=64, db_index=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=100, blank=True)
    price = models.CharField(max_length=64, blank=True)
    skills = models.TextField(blank=True)
    images = models.TextField(blank=True)
    seller_name = models.CharField(max_length=255, blank=True)
    discord_tag = models.CharField(max_length=128, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)
    views = models.IntegerField(default=0)
    status = models.CharField(max_length=32, default='Pending', db_index=True)

    class Meta:
        ordering = ['-id']

    def __str__(self):
        return self.title


TALENT_EXCEL_COLUMN_TO_FIELD = {
    'Name': 'name',
    'Role': 'role',
    'Injective Role': 'injective_role',
    'Experience': 'experience',
    'Education': 'education',
    'Location': 'location',
    'Availability': 'availability',
    'Monthly Rate': 'monthly_rate',
    'Skills': 'skills',
    'Languages': 'languages',
    'Discord': 'discord',
    'Email': 'email',
    'Phone': 'phone',
    'Telegram': 'telegram',
    'X': 'x',
    'Github': 'github',
    'Wallet Address': 'wallet_address',
    'Wallet Type': 'wallet_type',
    'NFT Holdings': 'nft_holdings',
    'Token Holdings': 'token_holdings',
    'Portfolio': 'portfolio',
    'CV': 'cv',
    'Image url': 'image_url',
    'Bio': 'bio',
    'Submission date': 'submission_date',
    'Status': 'status',
}


class Talent(models.Model):
    name = models.CharField(max_length=255)
    role = models.CharField(max_length=255, blank=True)
    injective_role = models.CharField(max_length=255, blank=True)
    experience = models.CharField(max_length=255, blank=True)
    education = models.CharField(max_length=255, blank=True)
    location = models.CharField(max_length=255, blank=True)
    availability = models.CharField(max_length=64, blank=True)
    monthly_rate = models.CharField(max_length=64, blank=True)
    skills = models.TextField(blank=True)
    languages = models.CharField(max_length=255, blank=True)
    discord = models.CharField(max_length=128, blank=True)
    email = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=64, blank=True)
    telegram = models.CharField(max_length=128, blank=True)
    x = models.CharField(max_length=128, blank=True)
    github = models.CharField(max_length=255, blank=True)
    wallet_address = models.CharField(max_length=64, db_index=True)
    wallet_type = models.CharField(max_length=64, blank=True)
    nft_holdings = models.TextField(blank=True)
    token_holdings = models.TextField(blank=True)
    portfolio = models.CharField(max_length=500, blank=True)
    cv = models.CharField(max_length=500, blank=True)
    image_url = models.CharField(max_length=500, blank=True)
    bio = models.TextField(blank=True)
    submission_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=32, default='Pending', db_index=True)

    class Meta:
        ordering = ['-id']

    def __str__(self):
        return f"{self.name} ({self.wallet_address})"

    def to_excel_dict(self):
        # Maps snake_case fields back to the original Excel column names so
        # downstream code (frontend, the Discord bot's DataFrame) sees the
        # same keys it always did.
        return {
            'Name': self.name,
            'Role': self.role,
            'Injective Role': self.injective_role,
            'Experience': self.experience,
            'Education': self.education,
            'Location': self.location,
            'Availability': self.availability,
            'Monthly Rate': self.monthly_rate,
            'Skills': self.skills,
            'Languages': self.languages,
            'Discord': self.discord,
            'Email': self.email,
            'Phone': self.phone,
            'Telegram': self.telegram,
            'X': self.x,
            'Github': self.github,
            'Wallet Address': self.wallet_address,
            'Wallet Type': self.wallet_type,
            'NFT Holdings': self.nft_holdings,
            'Token Holdings': self.token_holdings,
            'Portfolio': self.portfolio,
            'CV': self.cv,
            'Image url': self.image_url,
            'Bio': self.bio,
            'Submission date': (
                self.submission_date.strftime('%Y-%m-%d %H:%M:%S')
                if self.submission_date else ''
            ),
            'Status': self.status,
        }
