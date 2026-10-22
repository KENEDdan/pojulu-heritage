from django.contrib import admin
from .models import FamilyAccount

# Will is intentionally NOT registered here. Its content is encrypted at
# rest and should only ever be decrypted through the app's own controlled
# views (the account holder's own page, or the superadmin reveal flow in
# apps.dashboard) — not exposed through a generic admin change form.


@admin.register(FamilyAccount)
class FamilyAccountAdmin(admin.ModelAdmin):
    list_display  = ['person', 'user', 'is_active', 'must_change_password', 'created_by', 'created_at']
    list_filter   = ['is_active', 'must_change_password']
    search_fields = ['person__first_name', 'person__last_name', 'user__username']
    raw_id_fields = ['user', 'person', 'created_by']
    readonly_fields = ['created_at']
