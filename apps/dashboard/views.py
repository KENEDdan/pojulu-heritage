from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from apps.core.utils import search_term
from django.core.exceptions import PermissionDenied
from django.conf import settings
from django.views.decorators.http import require_POST
import logging
from django.urls import reverse
from django.db.models import Q
from django.http import Http404
from django.core.paginator import Paginator
from django.utils import timezone
from .forms import ClanMediaFormSet, PersonMediaFormSet, NewsMediaFormSet

from .models import AdminProfile, ROLE_CHOICES
from .forms import (
    CreateAdminForm, EditAdminForm,
    ClanForm, ClanChiefForm, ClanEventForm,
    PersonForm, FamilyForm,
    MemorialRecordForm, AchievementForm,
    MarriageForm, CulturalRecordForm,
    ElderInterviewForm, SubmissionReviewForm,
    FamilyAccountCredentialsForm, ResetPasswordForm, NewsPostForm,
    CLAN_FULL, PERSON_FULL, FAMILY_FULL, MEMORIAL_FULL,
    ACHIEVE_FULL, MARRIAGE_FULL, CULTURAL_FULL, ELDER_FULL, NEWS_FULL,
)
from apps.clans.models import Clan, ClanChief, ClanEvent, ClanBoma
from apps.genealogy.models import Person, Family
from apps.memorial.models import MemorialRecord
from apps.achievements.models import Achievement
from apps.marriages.models import Marriage
from apps.cultural.models import CulturalRecord
from apps.elders.models import ElderInterview
from apps.news.models import NewsPost
from apps.submissions.models import Submission
from apps.wills.models import FamilyAccount, Will

security_log = logging.getLogger('phf.security')


# ── DECORATORS ────────────────────────────────────────

def is_dashboard_user(user):
    if not user.is_authenticated or not user.is_active:
        return False
    if user.is_superuser:
        return True
    profile = getattr(user, 'admin_profile', None)
    return bool(profile and profile.is_active)


def get_role_redirect(user):
    if user.is_superuser:
        return reverse('dashboard:home')
    try:
        role = user.admin_profile.role
        return reverse({
            'clan_admin':        'dashboard:clan_dashboard',
            'genealogy_admin':   'dashboard:genealogy_dashboard',
            'memorial_admin':    'dashboard:memorial_dashboard',
            'cultural_admin':    'dashboard:cultural_dashboard',
            'elder_admin':       'dashboard:elder_dashboard',
            'achievement_admin': 'dashboard:achievement_dashboard',
            'content_admin':     'dashboard:content_dashboard',
        }.get(role, 'dashboard:login'))
    except AdminProfile.DoesNotExist:
        return reverse('core:home')


def require_superadmin(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('dashboard:login')
        if not request.user.is_superuser:
            security_log.warning('Permission denied (superadmin only): user=%s path=%s', request.user.username, request.path)
            if not is_dashboard_user(request.user):
                raise PermissionDenied
            messages.error(request, 'Only the Super Administrator can access this area.')
            return redirect(get_role_redirect(request.user))
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


def require_role(allowed_roles):
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('dashboard:login')
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            try:
                p = request.user.admin_profile
                if not p.is_active:
                    logout(request)
                    return redirect('dashboard:login')
                if p.role not in allowed_roles:
                    security_log.warning('Permission denied (role %s): user=%s path=%s', p.role, request.user.username, request.path)
                    messages.error(request, 'Your role does not have access to that section.')
                    return redirect(get_role_redirect(request.user))
            except AdminProfile.DoesNotExist:
                security_log.warning('Permission denied (no staff profile): user=%s path=%s', request.user.username, request.path)
                raise PermissionDenied
            return view_func(request, *args, **kwargs)
        wrapper.__name__ = view_func.__name__
        return wrapper
    return decorator


def paginate(request, object_list, per_page=None):
    per_page = per_page or settings.RECORDS_PER_PAGE
    return Paginator(object_list, per_page).get_page(request.GET.get('page'))


def _render_form(request, form, title, cancel_url, full_fields=None,
                 obj=None, delete_url=None, subtitle='', page_title=None, submit_label='Save Record',
                 media_formset=None, media_title='', media_help='', soft_delete=False):
    trash_wording = {
        'delete_heading': 'Move this record to the Trash?',
        'delete_message': 'It will disappear from the public site and the dashboards. '
                          'A Super Administrator can restore it from the Trash.',
        'delete_button':  'Move to Trash',
    } if soft_delete else {}
    return render(request, 'dashboard/form.html', {
        **trash_wording,
        'form':         form,
        'title':        title,
        'subtitle':     subtitle,
        'cancel_url':   cancel_url,
        'full_fields':  full_fields or [],
        'obj':          obj,
        'delete_url':   delete_url,
        'page_title':   page_title or title,
        'submit_label': submit_label,
        'media_formset': media_formset,
        'media_title':   media_title,
        'media_help':    media_help,
    })


# ── AUTH ──────────────────────────────────────────────

def dashboard_login(request):
    if is_dashboard_user(request.user):
        return redirect(get_role_redirect(request.user))
    error = None
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user is not None and is_dashboard_user(user):
            login(request, user)
            security_log.info('Dashboard login: user=%s', user.username)
            return redirect(get_role_redirect(user))
        if user is not None:
            security_log.warning('Dashboard login refused (no active staff access): user=%s', user.username)
        # Same message either way, so the form doesn't reveal which accounts exist.
        error = 'Invalid username or password, or this account has no dashboard access.'
    return render(request, 'dashboard/login.html', {'error': error})


@require_POST
def dashboard_logout(request):
    logout(request)
    return redirect('dashboard:login')


# ── SUPERADMIN HOME ───────────────────────────────────

@require_superadmin
def home(request):
    stats = {
        'clans':      Clan.objects.filter(is_verified=True).count(),
        'clans_draft': Clan.objects.filter(is_verified=False).count(),
        'persons':    Person.objects.filter(is_verified=True).count(),
        'families':   Family.objects.filter(is_verified=True).count(),
        'memorial':   MemorialRecord.objects.count(),
        'achievements': Achievement.objects.filter(is_verified=True).count(),
        'cultural':   CulturalRecord.objects.filter(is_verified=True).count(),
        'interviews': ElderInterview.objects.filter(is_published=True).count(),
        'marriages':  Marriage.objects.filter(is_verified=True).count(),
        'pending':    Submission.objects.filter(status='pending').count(),
        'admins':     AdminProfile.objects.filter(is_active=True).count(),
    }
    return render(request, 'dashboard/home.html', {
        'stats': stats,
        'recent_submissions': Submission.objects.filter(status='pending').order_by('-created_at')[:10],
        'admin_profiles': AdminProfile.objects.select_related('user').order_by('-created_at')[:6],
        'is_super': True,
    })


# ── ROLE DASHBOARDS ───────────────────────────────────
# Every table is paginated (settings.RECORDS_PER_PAGE). Persons, families,
# clans, interviews and news also take ?q= (name), ?clan= and ?status=.

STATUS_CHOICES = [('published', 'Published / verified'), ('draft', 'Draft / unverified')]


def table_filters(request):
    clan = request.GET.get('clan', '')
    status = request.GET.get('status', '')
    f = {'q': search_term(request), 'clan': clan if clan.isdigit() else '',
         'status': status if status in ('published', 'draft') else ''}
    f['active'] = any(f.values())
    return f


def apply_filters(qs, f, name_fields, status_field, clan_field='clan'):
    if f['q']:
        cond = Q()
        for name in name_fields:
            cond |= Q(**{f'{name}__icontains': f['q']})
        qs = qs.filter(cond)
    if f['clan'] and clan_field:
        qs = qs.filter(**{f'{clan_field}_id': int(f['clan'])})
    if f['status']:
        qs = qs.filter(**{status_field: f['status'] == 'published'})
    return qs


def filter_context(f, show_clan=True, placeholder='Search by name…'):
    return {'filters': f, 'status_choices': STATUS_CHOICES, 'filter_placeholder': placeholder,
            'filter_clans': Clan.objects.order_by('name').only('pk', 'name') if show_clan else None}


@require_role(['clan_admin', 'content_admin'])
def clan_dashboard(request):
    f = table_filters(request)
    clans = apply_filters(Clan.objects.with_counts().order_by('name'), f, ['name'], 'is_verified', clan_field=None)
    return render(request, 'dashboard/clan_dashboard.html', {
        'clans':        paginate(request, clans),
        'total':        Clan.objects.count(),
        'verified':     Clan.objects.filter(is_verified=True).count(),
        'draft':        Clan.objects.filter(is_verified=False).count(),
        'chiefs_total': ClanChief.objects.count(),
        'page_title':   'Clan Management',
        **filter_context(f, show_clan=False, placeholder='Search clans…'),
    })


@require_role(['genealogy_admin', 'content_admin'])
def genealogy_dashboard(request):
    f = table_filters(request)
    persons = apply_filters(Person.objects.select_related('clan').order_by('-created_at'), f,
                            ['first_name', 'middle_name', 'last_name', 'other_names'], 'is_verified')
    families = apply_filters(Family.objects.with_counts().select_related('clan').order_by('-created_at'), f,
                             ['name'], 'is_verified')
    return render(request, 'dashboard/genealogy_dashboard.html', {
        'persons':          paginate(request, persons),
        'families':         Paginator(families, settings.RECORDS_PER_PAGE).get_page(request.GET.get('fpage')),
        'total_persons':    Person.objects.count(),
        'verified_persons': Person.objects.filter(is_verified=True).count(),
        'total_families':   Family.objects.count(),
        'elders':           Person.objects.filter(is_elder=True).count(),
        'page_title':       'Genealogy & Families',
        **filter_context(f, placeholder='Search people or families…'),
    })


@require_role(['memorial_admin', 'content_admin'])
def memorial_dashboard(request):
    f = table_filters(request)
    memorials = apply_filters(MemorialRecord.objects.select_related('person', 'person__clan').order_by('-created_at'),
                              f, ['person__first_name', 'person__last_name'], 'person__is_verified', clan_field='person__clan')
    return render(request, 'dashboard/memorial_dashboard.html', {
        'memorials': paginate(request, memorials),
        'total':     MemorialRecord.objects.count(),
        'featured':  MemorialRecord.objects.filter(is_featured=True).count(),
        'page_title': 'Memorial Records',
    })


@require_role(['cultural_admin', 'content_admin'])
def cultural_dashboard(request):
    from django.db.models import Count
    from apps.cultural.models import RECORD_TYPE_CHOICES
    counts = dict(CulturalRecord.objects.values_list('record_type').annotate(n=Count('pk')))
    type_counts = {label: counts.get(val, 0) for val, label in RECORD_TYPE_CHOICES}
    f = table_filters(request)
    records = apply_filters(CulturalRecord.objects.select_related('clan').order_by('-created_at'), f,
                            ['title'], 'is_verified')
    return render(request, 'dashboard/cultural_dashboard.html', {
        'records':     paginate(request, records),
        'total':       CulturalRecord.objects.count(),
        'verified':    CulturalRecord.objects.filter(is_verified=True).count(),
        'type_counts': type_counts,
        'page_title':  'Cultural Archive',
    })


@require_role(['elder_admin', 'cultural_admin', 'content_admin'])
def elder_dashboard(request):
    f = table_filters(request)
    interviews = apply_filters(ElderInterview.objects.select_related('clan').order_by('-interview_date', '-created_at'),
                               f, ['elder_name', 'interviewer'], 'is_published')
    return render(request, 'dashboard/elder_dashboard.html', {
        'interviews':  paginate(request, interviews),
        'total':       ElderInterview.objects.count(),
        'published':   ElderInterview.objects.filter(is_published=True).count(),
        'unpublished': ElderInterview.objects.filter(is_published=False).count(),
        'with_audio':  ElderInterview.objects.exclude(audio_file='').exclude(audio_file__isnull=True).count(),
        'with_video':  ElderInterview.objects.exclude(video_url='').count(),
        'page_title':  'Elder Interviews',
        **filter_context(f, placeholder='Search elder or interviewer…'),
    })


@require_role(['achievement_admin', 'content_admin'])
def achievement_dashboard(request):
    from django.db.models import Count
    from apps.achievements.models import CATEGORY_CHOICES
    counts = dict(Achievement.objects.values_list('category').annotate(n=Count('pk')))
    cat_counts = {label: counts.get(val, 0) for val, label in CATEGORY_CHOICES}
    f = table_filters(request)
    achievements = apply_filters(Achievement.objects.select_related('clan').order_by('-created_at'), f,
                                 ['person_name', 'title'], 'is_verified')
    return render(request, 'dashboard/achievement_dashboard.html', {
        'achievements': paginate(request, achievements),
        'total':        Achievement.objects.count(),
        'verified':     Achievement.objects.filter(is_verified=True).count(),
        'featured':     Achievement.objects.filter(is_featured=True).count(),
        'cat_counts':   cat_counts,
        'page_title':   'Achievements',
    })


@require_role(['content_admin'])
def content_dashboard(request):
    return render(request, 'dashboard/content_dashboard.html', {
        'stats': {
            'clans':      Clan.objects.filter(is_verified=True).count(),
            'persons':    Person.objects.filter(is_verified=True).count(),
            'families':   Family.objects.filter(is_verified=True).count(),
            'memorial':   MemorialRecord.objects.count(),
            'achievements': Achievement.objects.filter(is_verified=True).count(),
            'cultural':   CulturalRecord.objects.filter(is_verified=True).count(),
            'interviews': ElderInterview.objects.filter(is_published=True).count(),
            'marriages':  Marriage.objects.filter(is_verified=True).count(),
            'pending':    Submission.objects.filter(status='pending').count(),
        },
        'recent_submissions': Submission.objects.filter(status='pending').order_by('-created_at')[:10],
        'page_title': 'Content Administration',
    })


# ── CLAN CRUD ─────────────────────────────────────────

@require_role(['clan_admin', 'content_admin'])
def clan_add(request):
    form = ClanForm(request.POST or None)
    media_formset = ClanMediaFormSet(request.POST or None, request.FILES or None, instance=Clan())
    if request.method == 'POST' and form.is_valid() and media_formset.is_valid():
        clan = form.save()
        media_formset.instance = clan
        media_formset.save()
        messages.success(request, f'✅ {clan.name} Clan created successfully.')
        return redirect('dashboard:clan_dashboard')
    return _render_form(request, form,
        title='Add New Clan',
        subtitle='Document a Pojulu clan — its history, origins, and cultural heritage.',
        cancel_url=reverse('dashboard:clan_dashboard'),
        full_fields=CLAN_FULL,
        media_formset=media_formset, media_title='Photos, Documents & Media for this Clan',
        media_help='Upload photos, PDFs, audio, or video for any section above (history, geography, boma, culture, leadership, etc.) — tag each item to the relevant section.',
        page_title='Add Clan', submit_label='Create Clan')


@require_role(['clan_admin', 'content_admin'])
def clan_edit(request, pk):
    clan = get_object_or_404(Clan, pk=pk)
    form = ClanForm(request.POST or None, instance=clan)
    media_formset = ClanMediaFormSet(request.POST or None, request.FILES or None, instance=clan)
    if request.method == 'POST' and form.is_valid() and media_formset.is_valid():
        form.save()
        media_formset.save()
        messages.success(request, f'✅ {clan.name} Clan updated.')
        return redirect('dashboard:clan_dashboard')
    return _render_form(request, form,
        title=f'Edit: {clan.name} Clan',
        subtitle='Update clan history, chiefs, cultural information, and publication status.',
        cancel_url=reverse('dashboard:clan_dashboard'),
        full_fields=CLAN_FULL, obj=clan,
        delete_url=reverse('dashboard:clan_delete', args=[pk]), soft_delete=True,
        media_formset=media_formset, media_title='Photos, Documents & Media for this Clan',
        media_help='Upload photos, PDFs, audio, or video for any section above — tag each item to the relevant section (history, geography, boma, culture, leadership, etc.).',
        page_title=f'Edit {clan.name} Clan')


@require_superadmin
@require_POST
def clan_delete(request, pk):
    clan = get_object_or_404(Clan, pk=pk)
    label = clan.name
    clan.soft_delete(request.user)
    security_log.warning('Moved to Trash: %s pk=%s "%s" by=%s', 'Clan', pk, label, request.user.username)
    messages.success(request, f'🗑️ "{label}" moved to the Trash. A Super Administrator can restore it from Trash.')
    return redirect('dashboard:clan_dashboard')


@require_role(['clan_admin', 'content_admin'])
def chief_add(request):
    form = ClanChiefForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        chief = form.save()
        messages.success(request, f'✅ {chief.name} added as {chief.title}.')
        return redirect('dashboard:clan_dashboard')
    return _render_form(request, form,
        title='Add Chief / Elder',
        subtitle='Record a traditional leader or elder in the clan leadership history.',
        cancel_url=reverse('dashboard:clan_dashboard'),
        full_fields=['notes'], page_title='Add Chief / Elder', submit_label='Add Leader')


@require_role(['clan_admin', 'content_admin'])
def chief_edit(request, pk):
    chief = get_object_or_404(ClanChief, pk=pk)
    form = ClanChiefForm(request.POST or None, instance=chief)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'✅ {chief.name} updated.')
        return redirect('dashboard:clan_dashboard')
    return _render_form(request, form,
        title=f'Edit: {chief.title} {chief.name}',
        cancel_url=reverse('dashboard:clan_dashboard'),
        full_fields=['notes'], obj=chief,
        delete_url=reverse('dashboard:chief_delete', args=[pk]),
        page_title=f'Edit {chief.name}')


@require_superadmin
@require_POST
def chief_delete(request, pk):
    chief = get_object_or_404(ClanChief, pk=pk)
    if request.method == 'POST':
        name = chief.name
        chief.delete()
        messages.success(request, f'🗑️ {name} deleted.')
    return redirect('dashboard:clan_dashboard')


@require_role(['clan_admin', 'content_admin'])
def event_add(request):
    form = ClanEventForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        event = form.save()
        messages.success(request, f'✅ Historical event "{event.title}" added.')
        return redirect('dashboard:clan_dashboard')
    return _render_form(request, form,
        title='Add Historical Event',
        subtitle='Record a significant historical event for a Pojulu clan.',
        cancel_url=reverse('dashboard:clan_dashboard'),
        full_fields=['description','significance'],
        page_title='Add Historical Event', submit_label='Add Event')


@require_role(['clan_admin', 'content_admin'])
def event_edit(request, pk):
    event = get_object_or_404(ClanEvent, pk=pk)
    form = ClanEventForm(request.POST or None, instance=event)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'✅ Event updated.')
        return redirect('dashboard:clan_dashboard')
    return _render_form(request, form,
        title=f'Edit Event: {event.title}',
        cancel_url=reverse('dashboard:clan_dashboard'),
        full_fields=['description','significance'], obj=event,
        delete_url=reverse('dashboard:event_delete', args=[pk]),
        page_title=f'Edit Event')


@require_superadmin
@require_POST
def event_delete(request, pk):
    event = get_object_or_404(ClanEvent, pk=pk)
    if request.method == 'POST':
        event.delete()
        messages.success(request, '🗑️ Event deleted.')
    return redirect('dashboard:clan_dashboard')


# ── PERSON CRUD ───────────────────────────────────────

@require_role(['genealogy_admin', 'memorial_admin', 'content_admin'])
def person_add(request):
    form = PersonForm(request.POST or None, request.FILES or None)
    media_formset = PersonMediaFormSet(request.POST or None, request.FILES or None, instance=Person())
    if request.method == 'POST' and form.is_valid() and media_formset.is_valid():
        person = form.save()
        media_formset.instance = person
        media_formset.save()
        messages.success(request, f'✅ {person.full_name} added to the archive.')
        return redirect('dashboard:genealogy_dashboard')
    return _render_form(request, form,
        title='Add Person',
        subtitle='Add an individual to the Pojulu genealogy archive.',
        cancel_url=reverse('dashboard:genealogy_dashboard'),
        full_fields=PERSON_FULL,
        media_formset=media_formset, media_title='Photos, Documents & Media for this Person',
        media_help='Upload profile photos, certificates, PDFs, audio, or video related to this person.',
        page_title='Add Person', submit_label='Save Person')


@require_role(['genealogy_admin', 'memorial_admin', 'content_admin'])
def person_edit(request, pk):
    person = get_object_or_404(Person, pk=pk)
    form = PersonForm(request.POST or None, request.FILES or None, instance=person)
    media_formset = PersonMediaFormSet(request.POST or None, request.FILES or None, instance=person)
    if request.method == 'POST' and form.is_valid() and media_formset.is_valid():
        form.save()
        media_formset.save()
        messages.success(request, f'✅ {person.full_name} updated.')
        return redirect('dashboard:genealogy_dashboard')
    return _render_form(request, form,
        title=f'Edit: {person.full_name}',
        subtitle='Update this person\'s biographical and genealogical information.',
        cancel_url=reverse('dashboard:genealogy_dashboard'),
        full_fields=PERSON_FULL, obj=person,
        delete_url=reverse('dashboard:person_delete', args=[pk]), soft_delete=True,
        media_formset=media_formset, media_title='Photos, Documents & Media for this Person',
        media_help='Upload profile photos, certificates, PDFs, audio, or video related to this person.',
        page_title=f'Edit {person.full_name}')


@require_superadmin
@require_POST
def person_delete(request, pk):
    person = get_object_or_404(Person, pk=pk)
    label = person.full_name
    person.soft_delete(request.user)
    security_log.warning('Moved to Trash: %s pk=%s "%s" by=%s', 'Person', pk, label, request.user.username)
    messages.success(request, f'🗑️ "{label}" moved to the Trash. A Super Administrator can restore it from Trash.')
    return redirect('dashboard:genealogy_dashboard')


# ── FAMILY CRUD ───────────────────────────────────────

@require_role(['genealogy_admin', 'content_admin'])
def family_add(request):
    form = FamilyForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        family = form.save()
        messages.success(request, f'✅ {family.name} created.')
        return redirect('dashboard:genealogy_dashboard')
    return _render_form(request, form,
        title='Add Family',
        subtitle='Create a family unit linked to a Pojulu clan.',
        cancel_url=reverse('dashboard:genealogy_dashboard'),
        full_fields=FAMILY_FULL,
        page_title='Add Family', submit_label='Create Family')


@require_role(['genealogy_admin', 'content_admin'])
def family_edit(request, pk):
    family = get_object_or_404(Family, pk=pk)
    form = FamilyForm(request.POST or None, instance=family)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'✅ {family.name} updated.')
        return redirect('dashboard:genealogy_dashboard')
    return _render_form(request, form,
        title=f'Edit: {family.name}',
        cancel_url=reverse('dashboard:genealogy_dashboard'),
        full_fields=FAMILY_FULL, obj=family,
        delete_url=reverse('dashboard:family_delete', args=[pk]), soft_delete=True,
        page_title=f'Edit {family.name}')


@require_superadmin
@require_POST
def family_delete(request, pk):
    family = get_object_or_404(Family, pk=pk)
    label = family.name
    family.soft_delete(request.user)
    security_log.warning('Moved to Trash: %s pk=%s "%s" by=%s', 'Family', pk, label, request.user.username)
    messages.success(request, f'🗑️ "{label}" moved to the Trash. A Super Administrator can restore it from Trash.')
    return redirect('dashboard:genealogy_dashboard')


# ── MEMORIAL CRUD ─────────────────────────────────────

@require_role(['memorial_admin', 'content_admin'])
def memorial_add(request):
    form = MemorialRecordForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        mem = form.save()
        messages.success(request, f'✅ Memorial record for {mem.person.full_name} created.')
        return redirect('dashboard:memorial_dashboard')
    return _render_form(request, form,
        title='Add Memorial Record',
        subtitle='Create an In Memoriam record honouring a Pojulu person who has passed.',
        cancel_url=reverse('dashboard:memorial_dashboard'),
        full_fields=MEMORIAL_FULL,
        page_title='Add Memorial Record', submit_label='Save Memorial')


@require_role(['memorial_admin', 'content_admin'])
def memorial_edit(request, pk):
    mem = get_object_or_404(MemorialRecord, pk=pk)
    form = MemorialRecordForm(request.POST or None, instance=mem)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'✅ Memorial for {mem.person.full_name} updated.')
        return redirect('dashboard:memorial_dashboard')
    return _render_form(request, form,
        title=f'Edit Memorial: {mem.person.full_name}',
        cancel_url=reverse('dashboard:memorial_dashboard'),
        full_fields=MEMORIAL_FULL, obj=mem,
        delete_url=reverse('dashboard:memorial_delete', args=[pk]), soft_delete=True,
        page_title=f'Edit Memorial: {mem.person.full_name}')


@require_superadmin
@require_POST
def memorial_delete(request, pk):
    mem = get_object_or_404(MemorialRecord, pk=pk)
    label = mem.person.full_name
    mem.soft_delete(request.user)
    security_log.warning('Moved to Trash: %s pk=%s "%s" by=%s', 'MemorialRecord', pk, label, request.user.username)
    messages.success(request, f'🗑️ "{label}" moved to the Trash. A Super Administrator can restore it from Trash.')
    return redirect('dashboard:memorial_dashboard')


# ── ACHIEVEMENT CRUD ──────────────────────────────────

@require_role(['achievement_admin', 'content_admin'])
def achievement_add(request):
    form = AchievementForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        ach = form.save()
        messages.success(request, f'✅ Achievement for {ach.person_name} added.')
        return redirect('dashboard:achievement_dashboard')
    return _render_form(request, form,
        title='Add Achievement',
        subtitle='Record a notable achievement by a Pojulu person.',
        cancel_url=reverse('dashboard:achievement_dashboard'),
        full_fields=ACHIEVE_FULL,
        page_title='Add Achievement', submit_label='Save Achievement')


@require_role(['achievement_admin', 'content_admin'])
def achievement_edit(request, pk):
    ach = get_object_or_404(Achievement, pk=pk)
    form = AchievementForm(request.POST or None, instance=ach)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'✅ Achievement updated.')
        return redirect('dashboard:achievement_dashboard')
    return _render_form(request, form,
        title=f'Edit: {ach.person_name}',
        cancel_url=reverse('dashboard:achievement_dashboard'),
        full_fields=ACHIEVE_FULL, obj=ach,
        delete_url=reverse('dashboard:achievement_delete', args=[pk]),
        page_title=f'Edit Achievement')


@require_superadmin
@require_POST
def achievement_delete(request, pk):
    ach = get_object_or_404(Achievement, pk=pk)
    if request.method == 'POST':
        ach.delete()
        messages.success(request, '🗑️ Achievement deleted.')
    return redirect('dashboard:achievement_dashboard')


# ── MARRIAGE CRUD ─────────────────────────────────────

@require_role(['genealogy_admin', 'content_admin'])
def marriage_add(request):
    form = MarriageForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        m = form.save()
        messages.success(request, f'✅ Marriage record for {m.husband_display} & {m.wife_display} created.')
        return redirect('dashboard:genealogy_dashboard')
    return _render_form(request, form,
        title='Add Marriage Record',
        subtitle='Record a marriage union connecting Pojulu families and clans.',
        cancel_url=reverse('dashboard:genealogy_dashboard'),
        full_fields=MARRIAGE_FULL,
        page_title='Add Marriage Record', submit_label='Save Marriage')


@require_role(['genealogy_admin', 'content_admin'])
def marriage_edit(request, pk):
    m = get_object_or_404(Marriage, pk=pk)
    form = MarriageForm(request.POST or None, instance=m)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'✅ Marriage record updated.')
        return redirect('dashboard:genealogy_dashboard')
    return _render_form(request, form,
        title=f'Edit Marriage: {m.husband_display} & {m.wife_display}',
        cancel_url=reverse('dashboard:genealogy_dashboard'),
        full_fields=MARRIAGE_FULL, obj=m,
        delete_url=reverse('dashboard:marriage_delete', args=[pk]),
        page_title='Edit Marriage Record')


@require_superadmin
@require_POST
def marriage_delete(request, pk):
    m = get_object_or_404(Marriage, pk=pk)
    if request.method == 'POST':
        m.delete()
        messages.success(request, '🗑️ Marriage record deleted.')
    return redirect('dashboard:genealogy_dashboard')


# ── CULTURAL RECORD CRUD ──────────────────────────────

@require_role(['cultural_admin', 'content_admin'])
def cultural_add(request):
    form = CulturalRecordForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        rec = form.save()
        messages.success(request, f'✅ "{rec.title}" added to Cultural Archive.')
        return redirect('dashboard:cultural_dashboard')
    return _render_form(request, form,
        title='Add Cultural Record',
        subtitle='Add a song, proverb, ceremony, story, or other cultural heritage item.',
        cancel_url=reverse('dashboard:cultural_dashboard'),
        full_fields=CULTURAL_FULL,
        page_title='Add Cultural Record', submit_label='Save Cultural Record')


@require_role(['cultural_admin', 'content_admin'])
def cultural_edit(request, pk):
    rec = get_object_or_404(CulturalRecord, pk=pk)
    form = CulturalRecordForm(request.POST or None, request.FILES or None, instance=rec)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'✅ "{rec.title}" updated.')
        return redirect('dashboard:cultural_dashboard')
    return _render_form(request, form,
        title=f'Edit: {rec.title}',
        cancel_url=reverse('dashboard:cultural_dashboard'),
        full_fields=CULTURAL_FULL, obj=rec,
        delete_url=reverse('dashboard:cultural_delete', args=[pk]),
        page_title=f'Edit Cultural Record')


@require_superadmin
@require_POST
def cultural_delete(request, pk):
    rec = get_object_or_404(CulturalRecord, pk=pk)
    if request.method == 'POST':
        title = rec.title
        rec.delete()
        messages.success(request, f'🗑️ "{title}" deleted.')
    return redirect('dashboard:cultural_dashboard')


# ── ELDER INTERVIEW CRUD ──────────────────────────────

@require_role(['elder_admin', 'cultural_admin', 'content_admin'])
def elder_add(request):
    form = ElderInterviewForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        iv = form.save()
        messages.success(request, f'✅ Interview with {iv.elder_name} saved.')
        return redirect('dashboard:elder_dashboard')
    return _render_form(request, form,
        title='Add Elder Interview',
        subtitle='Record an oral history interview with a Pojulu elder.',
        cancel_url=reverse('dashboard:elder_dashboard'),
        full_fields=ELDER_FULL,
        page_title='Add Elder Interview', submit_label='Save Interview')


@require_role(['elder_admin', 'cultural_admin', 'content_admin'])
def elder_edit(request, pk):
    iv = get_object_or_404(ElderInterview, pk=pk)
    form = ElderInterviewForm(request.POST or None, request.FILES or None, instance=iv)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'✅ Interview with {iv.elder_name} updated.')
        return redirect('dashboard:elder_dashboard')
    return _render_form(request, form,
        title=f'Edit Interview: {iv.elder_name}',
        cancel_url=reverse('dashboard:elder_dashboard'),
        full_fields=ELDER_FULL, obj=iv,
        delete_url=reverse('dashboard:elder_delete', args=[pk]), soft_delete=True,
        page_title=f'Edit Interview: {iv.elder_name}')


@require_superadmin
@require_POST
def elder_delete(request, pk):
    iv = get_object_or_404(ElderInterview, pk=pk)
    label = iv.elder_name
    iv.soft_delete(request.user)
    security_log.warning('Moved to Trash: %s pk=%s "%s" by=%s', 'ElderInterview', pk, label, request.user.username)
    messages.success(request, f'🗑️ "{label}" moved to the Trash. A Super Administrator can restore it from Trash.')
    return redirect('dashboard:elder_dashboard')


# ── NEWS CRUD ─────────────────────────────────────
# News was previously only editable through the Django admin, which is now
# off by default in production.

@require_role(['content_admin'])
def news_dashboard(request):
    return render(request, 'dashboard/news_dashboard.html', {
        'posts':      NewsPost.objects.select_related('author').order_by('-created_at')[:50],
        'total':      NewsPost.objects.count(),
        'published':  NewsPost.objects.filter(is_published=True).count(),
        'drafts':     NewsPost.objects.filter(is_published=False).count(),
        'page_title': 'News & Events',
    })


@require_role(['content_admin'])
def news_add(request):
    form = NewsPostForm(request.POST or None, request.FILES or None)
    media_formset = NewsMediaFormSet(request.POST or None, request.FILES or None, instance=NewsPost())
    if request.method == 'POST' and form.is_valid() and media_formset.is_valid():
        post = form.save(commit=False)
        post.author = request.user
        post.save()
        media_formset.instance = post
        media_formset.save()
        messages.success(request, f'✅ "{post.title}" saved.')
        return redirect('dashboard:news_dashboard')
    return _render_form(request, form,
        title='Add News Post or Event',
        subtitle='Publish news, events, announcements and community stories.',
        cancel_url=reverse('dashboard:news_dashboard'),
        full_fields=NEWS_FULL,
        media_formset=media_formset, media_title='Gallery & Attachments',
        page_title='Add News Post', submit_label='Save Post')


@require_role(['content_admin'])
def news_edit(request, pk):
    post = get_object_or_404(NewsPost, pk=pk)
    form = NewsPostForm(request.POST or None, request.FILES or None, instance=post)
    media_formset = NewsMediaFormSet(request.POST or None, request.FILES or None, instance=post)
    if request.method == 'POST' and form.is_valid() and media_formset.is_valid():
        form.save()
        media_formset.save()
        messages.success(request, f'✅ "{post.title}" updated.')
        return redirect('dashboard:news_dashboard')
    return _render_form(request, form,
        title=f'Edit: {post.title}',
        cancel_url=reverse('dashboard:news_dashboard'),
        full_fields=NEWS_FULL, obj=post,
        delete_url=reverse('dashboard:news_delete', args=[pk]), soft_delete=True,
        media_formset=media_formset, media_title='Gallery & Attachments',
        page_title='Edit News Post')


@require_superadmin
@require_POST
def news_delete(request, pk):
    post = get_object_or_404(NewsPost, pk=pk)
    label = post.title
    post.soft_delete(request.user)
    security_log.warning('Moved to Trash: %s pk=%s "%s" by=%s', 'NewsPost', pk, label, request.user.username)
    messages.success(request, f'🗑️ "{label}" moved to the Trash. A Super Administrator can restore it from Trash.')
    return redirect('dashboard:news_dashboard')


# ── SUBMISSION REVIEW ─────────────────────────────────

@require_role(['content_admin'])
def submission_list(request):
    subs = Submission.objects.order_by('-created_at')
    status_filter = request.GET.get('status', '')
    if status_filter:
        subs = subs.filter(status=status_filter)
    return render(request, 'dashboard/submissions.html', {
        'submissions':     paginate(request, subs),
        'status_filter':   status_filter,
        'pending_count':   Submission.objects.filter(status='pending').count(),
        'page_title':      'Submission Review',
    })


@require_role(['content_admin'])
def submission_review(request, pk):
    sub = get_object_or_404(Submission, pk=pk)
    form = SubmissionReviewForm(request.POST or None, instance=sub)
    if request.method == 'POST' and form.is_valid():
        reviewed = form.save(commit=False)
        reviewed.reviewed_by = request.user
        reviewed.save()
        messages.success(request, f'✅ Submission status updated to: {sub.get_status_display()}')
        return redirect('dashboard:submission_list')
    return render(request, 'dashboard/submission_detail.html', {
        'sub':        sub,
        'form':       form,
        'cancel_url': reverse('dashboard:submission_list'),
        'page_title': f'Review: {sub.subject_name}',
    })


# ── TRASH (soft-deleted records) ──────────────────

TRASH_MODELS = {
    'clan':      (Clan, 'Clan'),
    'family':    (Family, 'Family'),
    'person':    (Person, 'Person'),
    'memorial':  (MemorialRecord, 'Memorial'),
    'interview': (ElderInterview, 'Elder Interview'),
    'news':      (NewsPost, 'News Post'),
}


def _trash_object(kind, pk):
    if kind not in TRASH_MODELS:
        raise Http404
    model = TRASH_MODELS[kind][0]
    return get_object_or_404(model.all_objects, pk=pk, is_deleted=True)


@require_superadmin
def trash(request):
    kind = request.GET.get('type', '')
    rows = []
    for key, (model, label) in TRASH_MODELS.items():
        if kind and key != kind:
            continue
        for obj in model.all_objects.filter(is_deleted=True).select_related('deleted_by').order_by('-deleted_at')[:200]:
            rows.append({'kind': key, 'label': label, 'obj': obj})
    rows.sort(key=lambda r: r['obj'].deleted_at or timezone.now(), reverse=True)
    return render(request, 'dashboard/trash.html', {
        'page_obj': paginate(request, rows),
        'kinds': [(k, label) for k, (_, label) in TRASH_MODELS.items()],
        'kind': kind,
        'page_title': 'Trash',
    })


@require_superadmin
@require_POST
def trash_restore(request, kind, pk):
    obj = _trash_object(kind, pk)
    obj.restore()
    security_log.warning('Restored from Trash: %s pk=%s by=%s', kind, pk, request.user.username)
    messages.success(request, f'♻️ "{obj}" restored.')
    return redirect('dashboard:trash')


@require_superadmin
@require_POST
def trash_purge(request, kind, pk):
    obj = _trash_object(kind, pk)
    if kind == 'person' and hasattr(obj, 'family_account'):
        messages.error(request, f'"{obj}" has a family (will) account. Deleting them permanently would also destroy '
                                f'their will, so this is blocked. Deactivate the family account first and keep the record in Trash.')
        return redirect('dashboard:trash')
    label = str(obj)
    obj.delete()
    security_log.warning('Permanently deleted: %s pk=%s "%s" by=%s', kind, pk, label, request.user.username)
    messages.success(request, f'"{label}" was permanently deleted.')
    return redirect('dashboard:trash')


# ── ACTIVITY LOG (django-simple-history) ──────────

AUDITED_MODELS = {
    'clan':        (Clan, 'history'),
    'clanchief':   (ClanChief, 'history'),
    'clanevent':   (ClanEvent, 'history'),
    'clanboma':    (ClanBoma, 'change_history'),
    'family':      (Family, 'history'),
    'person':      (Person, 'history'),
    'memorial':    (MemorialRecord, 'history'),
    'achievement': (Achievement, 'history'),
    'marriage':    (Marriage, 'history'),
    'cultural':    (CulturalRecord, 'history'),
    'interview':   (ElderInterview, 'history'),
    'news':        (NewsPost, 'history'),
    'adminprofile': (AdminProfile, 'history'),
    'familyaccount': (FamilyAccount, 'history'),
}
ACTIVITY_LOG_LIMIT = 1000
IGNORED_DIFF_FIELDS = {'updated_at', 'deleted_at', 'deleted_by'}


def _describe(record):
    if record.history_type == '+':
        return 'Created', []
    if record.history_type == '-':
        return 'Deleted permanently', []
    prev = record.prev_record
    if prev is None:
        return 'Updated', []
    changed = [c.field for c in record.diff_against(prev).changes if c.field not in IGNORED_DIFF_FIELDS]
    # is_deleted is not user-editable, so diff_against() skips it; compare directly.
    was, now = getattr(prev, 'is_deleted', None), getattr(record, 'is_deleted', None)
    if was is not None and was != now:
        return ('Moved to Trash' if now else 'Restored from Trash'), changed
    return 'Updated', changed


@require_superadmin
def activity_log(request):
    model_key = request.GET.get('model', '')
    user_id = request.GET.get('user', '')
    records = []
    for key, (model, manager) in AUDITED_MODELS.items():
        if model_key and key != model_key:
            continue
        qs = getattr(model, manager).select_related('history_user').order_by('-history_date')
        if user_id.isdigit():
            qs = qs.filter(history_user_id=int(user_id))
        records += [(key, r) for r in qs[:ACTIVITY_LOG_LIMIT]]
    records.sort(key=lambda kr: kr[1].history_date, reverse=True)
    page_obj = paginate(request, records[:ACTIVITY_LOG_LIMIT])
    page_obj.object_list = [
        {'model': model._meta.verbose_name.title(), 'record': r, 'action': action, 'changed': changed}
        for key, r in page_obj.object_list
        for model in [AUDITED_MODELS[key][0]]
        for action, changed in [_describe(r)]
    ]
    return render(request, 'dashboard/activity_log.html', {
        'page_obj': page_obj,
        'models': [(k, m._meta.verbose_name.title()) for k, (m, _) in AUDITED_MODELS.items()],
        'users': User.objects.filter(Q(is_superuser=True) | Q(admin_profile__isnull=False)).order_by('username'),
        'model_key': model_key, 'user_id': user_id,
        'page_title': 'Activity Log',
    })


# ── ACCOUNT MANAGEMENT ────────────────────────────────

@require_superadmin
def manage_accounts(request):
    return render(request, 'dashboard/accounts.html', {
        'admins': paginate(request, AdminProfile.objects.select_related('user', 'assigned_by').order_by('-created_at')),
    })


@require_superadmin
def create_account(request):
    form = CreateAdminForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        d = form.cleaned_data
        user = User.objects.create_user(
            username=d['username'], email=d['email'], password=d['password'],
            first_name=d['first_name'], last_name=d['last_name'], is_staff=True,
        )
        profile = AdminProfile.objects.create(
            user=user, role=d['role'],
            phone=d.get('phone', ''), notes=d.get('notes', ''),
            assigned_by=request.user,
        )
        profile.assign_permissions()
        security_log.warning('Staff account created: target=%s role=%s by=%s', user.username, profile.role, request.user.username)
        messages.success(request, f'✅ Account created for {user.get_full_name() or user.username}.')
        return redirect('dashboard:accounts')
    return _render_form(request, form,
        title='Create Administrator Account',
        subtitle='Create a staff login account with a specific role and section access.',
        cancel_url=reverse('dashboard:accounts'),
        full_fields=['notes'],
        page_title='Create Admin Account', submit_label='Create Account')


@require_superadmin
def edit_account(request, pk):
    profile = get_object_or_404(AdminProfile, pk=pk)
    form = EditAdminForm(request.POST or None, instance=profile,
                         initial={'first_name': profile.user.first_name,
                                  'last_name':  profile.user.last_name,
                                  'email':       profile.user.email})
    if request.method == 'POST' and form.is_valid():
        profile.user.first_name = form.cleaned_data['first_name']
        profile.user.last_name  = form.cleaned_data['last_name']
        profile.user.email      = form.cleaned_data['email']
        profile.user.save()
        old_role = AdminProfile.objects.get(pk=profile.pk).role
        form.save()
        profile.assign_permissions()
        security_log.warning('Staff account updated: target=%s role=%s->%s active=%s by=%s',
                             profile.user.username, old_role, profile.role, profile.is_active, request.user.username)
        messages.success(request, '✅ Account updated.')
        return redirect('dashboard:accounts')
    return _render_form(request, form,
        title=f'Edit Account: {profile.user.get_full_name() or profile.user.username}',
        cancel_url=reverse('dashboard:accounts'),
        full_fields=['notes'], obj=profile,
        delete_url=reverse('dashboard:deactivate_account', args=[pk]),
        page_title='Edit Admin Account')


@require_superadmin
@require_POST
def deactivate_account(request, pk):
    profile = get_object_or_404(AdminProfile, pk=pk)
    if request.method == 'POST':
        profile.is_active = False; profile.save()
        profile.user.is_active = False; profile.user.save()
        security_log.warning('Staff account deactivated: target=%s by=%s', profile.user.username, request.user.username)
        messages.success(request, f'{profile.user.get_full_name()} deactivated.')
    return redirect('dashboard:accounts')


@require_superadmin
@require_POST
def reactivate_account(request, pk):
    profile = get_object_or_404(AdminProfile, pk=pk)
    if request.method == 'POST':
        profile.is_active = True; profile.save()
        profile.user.is_active = True; profile.user.save()
        security_log.warning('Staff account reactivated: target=%s by=%s', profile.user.username, request.user.username)
        messages.success(request, f'{profile.user.get_full_name()} reactivated.')
    return redirect('dashboard:accounts')


# ── FAMILY (WILL) ACCOUNT MANAGEMENT ──────────────────
# Family accounts are private, non-staff logins (they never touch /admin/
# or /dashboard/) that let an individual write their own will in secret.
# Creation always ends with the account linked to a Person: either an
# existing verified record, or one created inline here — the link is what
# lets family_dashboard() work out who the will should be revealed to.

@require_superadmin
def family_account_list(request):
    return render(request, 'dashboard/family_accounts.html', {
        'accounts': paginate(request, FamilyAccount.objects.select_related('user', 'person', 'will').order_by('-created_at')),
        'page_title': 'Family (Will) Accounts',
    })


@require_superadmin
def family_account_search(request):
    q = request.GET.get('q', '').strip()
    results = Person.objects.none()
    if q:
        results = Person.objects.filter(
            Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(other_names__icontains=q)
        ).filter(family_account__isnull=True).select_related('clan')[:20]
    return render(request, 'dashboard/family_account_search.html', {
        'q': q, 'results': results,
        'page_title': 'New Family Account',
    })


@require_superadmin
def family_account_create_existing(request, person_id):
    person = get_object_or_404(Person, pk=person_id)
    if hasattr(person, 'family_account'):
        messages.error(request, f'{person.full_name} already has a family account.')
        return redirect('dashboard:family_account_list')
    form = FamilyAccountCredentialsForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        d = form.cleaned_data
        user = User.objects.create_user(username=d['username'], email=d['email'], password=d['password'], is_staff=False)
        FamilyAccount.objects.create(user=user, person=person, created_by=request.user)
        messages.success(request, f'✅ Family account created for {person.full_name}.')
        return redirect('dashboard:family_account_list')
    return _render_form(request, form,
        title=f'Create Family Account for {person.full_name}',
        subtitle='This creates a private login they can use to write their will. It stays secret from everyone, including family, until you reveal it.',
        cancel_url=reverse('dashboard:family_account_search'),
        page_title='Create Family Account', submit_label='Create Account')


@require_superadmin
def family_account_create_new_person(request):
    person_form = PersonForm(request.POST or None, request.FILES or None)
    account_form = FamilyAccountCredentialsForm(request.POST or None)
    if request.method == 'POST' and person_form.is_valid() and account_form.is_valid():
        person = person_form.save()
        d = account_form.cleaned_data
        user = User.objects.create_user(username=d['username'], email=d['email'], password=d['password'], is_staff=False)
        FamilyAccount.objects.create(user=user, person=person, created_by=request.user)
        messages.success(request, f'✅ {person.full_name} added to the archive and a family account created.')
        return redirect('dashboard:family_account_list')
    return render(request, 'dashboard/family_account_new_person.html', {
        'person_form': person_form, 'account_form': account_form,
        'full_fields': PERSON_FULL,
        'cancel_url': reverse('dashboard:family_account_search'),
        'page_title': 'Create Person & Family Account',
    })


@require_superadmin
@require_POST
def family_account_deactivate(request, pk):
    account = get_object_or_404(FamilyAccount, pk=pk)
    if request.method == 'POST':
        account.is_active = False; account.save()
        account.user.is_active = False; account.user.save()
        messages.success(request, f"{account.person.full_name}'s family account deactivated.")
    return redirect('dashboard:family_account_list')


@require_superadmin
@require_POST
def family_account_reactivate(request, pk):
    account = get_object_or_404(FamilyAccount, pk=pk)
    if request.method == 'POST':
        account.is_active = True; account.save()
        account.user.is_active = True; account.user.save()
        messages.success(request, f"{account.person.full_name}'s family account reactivated.")
    return redirect('dashboard:family_account_list')


@require_superadmin
def family_account_reset_password(request, pk):
    account = get_object_or_404(FamilyAccount, pk=pk)
    form = ResetPasswordForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        account.user.set_password(form.cleaned_data['password'])
        account.user.save()
        account.must_change_password = True
        account.save()
        messages.success(request, f"Password reset for {account.person.full_name}. They'll be asked to change it on next login.")
        return redirect('dashboard:family_account_list')
    return _render_form(request, form,
        title=f'Reset Password: {account.person.full_name}',
        cancel_url=reverse('dashboard:family_account_list'),
        page_title='Reset Password', submit_label='Reset Password')


@require_superadmin
def will_reveal(request, pk):
    # The content is encrypted with a passphrase only the will's owner ever
    # knew, never stored anywhere — this view has no way to decrypt or
    # preview it, by design. Revealing only flips visibility; it grants no
    # one here any decryption ability they didn't already have.
    will = get_object_or_404(Will, pk=pk)
    if request.method == 'POST':
        if not will.is_revealed:
            will.is_revealed = True
            will.revealed_by = request.user
            will.revealed_at = timezone.now()
            will.save()
            messages.success(request, f"{will.account.person.full_name}'s will has been revealed to their immediate family.")
        return redirect('dashboard:family_account_list')
    return render(request, 'dashboard/will_reveal_confirm.html', {
        'will': will,
        'page_title': f'Reveal Will: {will.account.person.full_name}',
    })