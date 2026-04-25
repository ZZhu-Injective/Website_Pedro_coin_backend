from django.contrib import admin

from .models import EligibleAddress


@admin.register(EligibleAddress)
class EligibleAddressAdmin(admin.ModelAdmin):
    list_display = ('address', 'note', 'added_at')
    search_fields = ('address', 'note')
    list_filter = ('added_at',)
    ordering = ('-added_at',)
