from django.contrib import admin
from django.utils.html import format_html
from .models import Clan, ClanChief, ClanEvent, ClanBoma, ClanMedia


class ClanChiefInline(admin.TabularInline):
    model        = ClanChief
    extra        = 1
    fields       = ['name', 'title', 'start_year', 'end_year', 'photo', 'order', 'notes']
    ordering     = ['order']


class ClanEventInline(admin.TabularInline):
    model    = ClanEvent
    extra    = 1
    fields   = ['title', 'year', 'description', 'significance']
    ordering = ['year']


class ClanBomaInline(admin.StackedInline):
    model        = ClanBoma
    extra        = 0
    fields       = ['name', 'current_leader', 'population', 'year_established',
                    'history', 'past_leaders', 'main_activities',
                    'location_description', 'infrastructure', 'notable_persons', 'order']
    ordering     = ['order']
    show_change_link = True


class ClanMediaInline(admin.TabularInline):
    model    = ClanMedia
    extra    = 2
    fields   = ['section', 'media_type', 'title', 'file', 'video_url', 'caption', 'boma', 'order']
    ordering = ['section', 'order']


@admin.register(Clan)
class ClanAdmin(admin.ModelAdmin):
    list_display        = ['name', 'payam', 'population_estimate', 'is_verified', 'is_featured', 'person_count', 'family_count']
    list_filter         = ['payam', 'is_verified', 'is_featured']
    search_fields       = ['name', 'description', 'origin_story']
    prepopulated_fields = {'slug': ('name',)}
    list_editable       = ['is_verified', 'is_featured']
    inlines             = [ClanChiefInline, ClanBomaInline, ClanEventInline, ClanMediaInline]
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'payam', 'tagline', 'description', 'is_verified', 'is_featured')
        }),
        ('History & Origins', {
            'fields': ('origin_story', 'migration_history', 'territorial_notes', 'historical_events'),
            'classes': ('collapse',)
        }),
        ('Culture & Beliefs', {
            'fields': ('cultural_practices', 'traditional_beliefs'),
            'classes': ('collapse',)
        }),
        ('Geography & Borders', {
            'fields': ('population_estimate', 'border_north', 'border_south', 'border_east', 'border_west', 'rivers', 'landscape'),
            'classes': ('collapse',)
        }),
        ('Livelihood & Infrastructure', {
            'fields': ('main_activities', 'infrastructure'),
            'classes': ('collapse',)
        }),
        ('Connections', {
            'fields': ('allied_clans', 'sub_clans'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ['created_at', 'updated_at']

    def person_count(self, obj):
        return format_html('<b>{}</b>', obj.person_count)
    person_count.short_description = 'Persons'


@admin.register(ClanChief)
class ClanChiefAdmin(admin.ModelAdmin):
    list_display  = ['name', 'title', 'clan', 'tenure', 'order']
    list_filter   = ['clan']
    search_fields = ['name', 'clan__name']
    ordering      = ['clan', 'order']


@admin.register(ClanBoma)
class ClanBomaAdmin(admin.ModelAdmin):
    list_display  = ['name', 'clan', 'current_leader', 'population', 'order']
    list_filter   = ['clan']
    search_fields = ['name', 'history', 'clan__name']
    inlines       = [ClanMediaInline]
    fieldsets = (
        ('Boma Identity', {
            'fields': ('clan', 'name', 'year_established', 'population', 'order')
        }),
        ('Leadership', {
            'fields': ('current_leader', 'past_leaders')
        }),
        ('History & Location', {
            'fields': ('history', 'location_description', 'main_activities', 'infrastructure', 'notable_persons', 'notes')
        }),
    )


@admin.register(ClanMedia)
class ClanMediaAdmin(admin.ModelAdmin):
    list_display  = ['title', 'clan', 'section', 'media_type', 'boma', 'order']
    list_filter   = ['clan', 'section', 'media_type']
    search_fields = ['title', 'caption', 'clan__name']
    ordering      = ['clan', 'section', 'order']


@admin.register(ClanEvent)
class ClanEventAdmin(admin.ModelAdmin):
    list_display  = ['title', 'clan', 'year']
    list_filter   = ['clan']
    search_fields = ['title', 'description']
    ordering      = ['clan', 'year']