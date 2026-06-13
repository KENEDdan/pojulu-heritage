from django.contrib import admin
from .models import Announcement, SiteStats


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display  = ['title', 'is_active', 'created_at']
    list_editable = ['is_active']
    search_fields = ['title', 'body']


@admin.register(SiteStats)
class SiteStatsAdmin(admin.ModelAdmin):
    list_display = ['clans_count', 'families_count', 'persons_count', 'memorial_count', 'interviews_count', 'updated_at']