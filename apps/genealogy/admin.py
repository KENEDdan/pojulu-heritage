from django.contrib import admin
from django.utils.html import format_html
from .models import Person, Family, PersonEducation, PersonCareer, PersonMedia


class PersonEducationInline(admin.StackedInline):
    model        = PersonEducation
    extra        = 0
    fields       = ['qualification', 'institution', 'field_of_study', 'start_year', 'end_year', 'is_current', 'honors', 'notes', 'certificate', 'order']
    ordering     = ['order']
    show_change_link = False


class PersonCareerInline(admin.StackedInline):
    model    = PersonCareer
    extra    = 0
    fields   = ['position', 'employer', 'location', 'start_year', 'end_year', 'is_current', 'description', 'order']
    ordering = ['order']


class PersonMediaInline(admin.TabularInline):
    model    = PersonMedia
    extra    = 2
    fields   = ['media_type', 'title', 'file', 'video_url', 'caption', 'date_taken', 'is_profile_photo', 'order']
    ordering = ['order']


@admin.register(Family)
class FamilyAdmin(admin.ModelAdmin):
    list_display  = ['name', 'clan', 'payam', 'member_count', 'is_verified']
    list_filter   = ['clan', 'payam', 'is_verified']
    search_fields = ['name', 'description']
    list_editable = ['is_verified']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Family Identity', {'fields': ('name', 'slug', 'clan', 'payam', 'origin_village', 'description', 'is_verified')}),
        ('Timestamps',      {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display  = ['full_name', 'clan', 'family', 'payam', 'birth_year', 'is_deceased', 'is_elder', 'is_verified']
    list_filter   = ['clan', 'payam', 'is_verified', 'is_deceased', 'is_elder', 'gender']
    search_fields = ['first_name', 'last_name', 'middle_name', 'biography', 'other_names']
    list_editable = ['is_verified']
    raw_id_fields = ['father', 'mother', 'clan', 'family']
    inlines       = [PersonEducationInline, PersonCareerInline, PersonMediaInline]
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Identity', {
            'fields': ('first_name', 'middle_name', 'last_name', 'other_names', 'slug', 'gender', 'photo')
        }),
        ('Heritage', {
            'fields': ('clan', 'family', 'payam')
        }),
        ('Parents', {
            'fields': ('father', 'mother')
        }),
        ('Birth & Death', {
            'fields': ('birth_year', 'birth_date', 'birth_place', 'is_deceased', 'death_year', 'death_date', 'death_place')
        }),
        ('Contact & Location', {
            'fields': ('phone', 'email_contact', 'address', 'current_residence'),
            'classes': ('collapse',)
        }),
        ('Biography & Skills', {
            'fields': ('biography', 'occupation', 'hobbies', 'skills_talents', 'languages_spoken', 'religion'),
            'classes': ('collapse',)
        }),
        ('Contributions', {
            'fields': ('contributions',),
            'classes': ('collapse',)
        }),
        ('Documents', {
            'fields': ('profile_pdf',),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('is_verified', 'is_elder', 'submitted_by')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def full_name(self, obj):
        return format_html('<b>{}</b>', obj.full_name)
    full_name.short_description = 'Full Name'


@admin.register(PersonEducation)
class PersonEducationAdmin(admin.ModelAdmin):
    list_display  = ['qualification', 'institution', 'person', 'period', 'is_current']
    list_filter   = ['is_current']
    search_fields = ['qualification', 'institution', 'person__first_name', 'person__last_name']
    raw_id_fields = ['person']


@admin.register(PersonCareer)
class PersonCareerAdmin(admin.ModelAdmin):
    list_display  = ['position', 'employer', 'person', 'period', 'is_current']
    list_filter   = ['is_current']
    search_fields = ['position', 'employer', 'person__first_name', 'person__last_name']
    raw_id_fields = ['person']


@admin.register(PersonMedia)
class PersonMediaAdmin(admin.ModelAdmin):
    list_display  = ['title', 'person', 'media_type', 'is_profile_photo', 'order']
    list_filter   = ['media_type', 'is_profile_photo']
    search_fields = ['title', 'caption', 'person__first_name', 'person__last_name']
    raw_id_fields = ['person']