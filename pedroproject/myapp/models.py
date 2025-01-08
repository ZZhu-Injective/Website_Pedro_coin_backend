from django.db import models

class TokenHolder(models.Model):
    address = models.CharField(max_length=255, unique=True)
    native_value = models.FloatField(default=0)
    cw20_value = models.FloatField(default=0)
    total_value = models.FloatField(default=0)
    percentage = models.FloatField(default=0)

    def __str__(self):
        return self.key
