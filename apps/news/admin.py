from django.contrib import admin
from .models import NewsPost, NewsMedia


class NewsMediaInline(admin.TabularInline):
    model   = NewsMedia
    extra   = 2
    fields  = ['media_type', 'title', 'file', 'caption', 'order']


@admin.register(NewsPost)
class NewsPostAdmin(admin.ModelAdmin):
    list_display   = ['title', 'post_type', 'is_published', 'is_featured', 'published_at', 'views']
    list_filter    = ['post_type', 'is_published', 'is_featured']
    search_fields  = ['title', 'excerpt', 'content']
    list_editable  = ['is_published', 'is_featured']
    prepopulated_fields = {'slug': ('title',)}
    date_hierarchy = 'published_at'
    inlines        = [NewsMediaInline]
    readonly_fields = ['views', 'created_at', 'updated_at']
    fieldsets = (
        ('Content', {
            'fields': ('title', 'slug', 'post_type', 'excerpt', 'content', 'cover_image', 'video_url', 'tags')
        }),
        ('Event Details', {
            'fields': ('event_date', 'event_end_date', 'event_location', 'is_upcoming'),
            'classes': ('collapse',),
            'description': 'Only fill this section for event posts.'
        }),
        ('Publishing', {
            'fields': ('is_published', 'is_featured', 'published_at', 'author')
        }),
        ('Statistics', {
            'fields': ('views', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )