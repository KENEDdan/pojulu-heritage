from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from .forms import ClanMediaFormSet, PersonMediaFormSet

from .models import AdminProfile, ROLE_CHOICES
from .forms import (
    CreateAdminForm, EditAdminForm,
    ClanForm, ClanChiefForm, ClanEventForm,
    PersonForm, FamilyForm,
    MemorialRecordForm, AchievementForm,
    MarriageForm, CulturalRecordForm,
    ElderInterviewForm, SubmissionReviewForm,
    CLAN_FULL, PERSON_FULL, FAMILY_FULL, MEMORIAL_FULL,
    ACHIEVE_FULL, MARRIAGE_FULL, CULTURAL_FULL, ELDER_FULL,
)
from apps.clans.models import Clan, ClanChief, ClanEvent
from apps.genealogy.models import Person, Family
from apps.memorial.models import MemorialRecord
from apps.achievements.models import Achievement
from apps.marriages.models import Marriage
from apps.cultural.models import CulturalRecord
from apps.elders.models import ElderInterview
from apps.submissions.models import Submission


# ── DECORATORS ────────────────────────────────────────

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
        }.get(role, 'dashboard:home'))
    except AdminProfile.DoesNotExist:
        return reverse('dashboard:home')


def require_dashboard(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('dashboard:login')
        if not request.user.is_superuser:
            try:
                p = request.user.admin_profile
                if not p.is_active:
                    logout(request)
                    return redirect('dashboard:login')
            except AdminProfile.DoesNotExist:
                raise PermissionDenied
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


def require_superadmin(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('dashboard:login')
        if not request.user.is_superuser:
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
                    return redirect(get_role_redirect(request.user))
            except AdminProfile.DoesNotExist:
                raise PermissionDenied
            return view_func(request, *args, **kwargs)
        wrapper.__name__ = view_func.__name__
        return wrapper
    return decorator


def _render_form(request, form, title, cancel_url, full_fields=None,
                 obj=None, delete_url=None, subtitle='', page_title=None, submit_label='Save Record',
                 media_formset=None, media_title='', media_help=''):
    return render(request, 'dashboard/form.html', {
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
    if request.user.is_authenticated:
        return redirect(get_role_redirect(request.user))
    error = None
    if request.method == 'POST':
        user = authenticate(request,
                            username=request.POST.get('username', '').strip(),
                            password=request.POST.get('password', ''))
        if user:
            if user.is_superuser or (hasattr(user, 'admin_profile') and user.admin_profile.is_active):
                login(request, user)
                return redirect(get_role_redirect(user))
            else:
                error = 'Your account has been deactivated or you do not have staff access.'
        else:
            error = 'Invalid username or password.'
    return render(request, 'dashboard/login.html', {'error': error})


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

@require_role(['clan_admin', 'content_admin'])
def clan_dashboard(request):
    return render(request, 'dashboard/clan_dashboard.html', {
        'clans':        Clan.objects.order_by('-created_at')[:30],
        'total':        Clan.objects.count(),
        'verified':     Clan.objects.filter(is_verified=True).count(),
        'draft':        Clan.objects.filter(is_verified=False).count(),
        'chiefs_total': ClanChief.objects.count(),
        'page_title':   'Clan Management',
    })


@require_role(['genealogy_admin', 'content_admin'])
def genealogy_dashboard(request):
    return render(request, 'dashboard/genealogy_dashboard.html', {
        'persons':          Person.objects.select_related('clan').order_by('-created_at')[:25],
        'families':         Family.objects.select_related('clan').order_by('-created_at')[:15],
        'total_persons':    Person.objects.count(),
        'verified_persons': Person.objects.filter(is_verified=True).count(),
        'total_families':   Family.objects.count(),
        'elders':           Person.objects.filter(is_elder=True).count(),
        'page_title':       'Genealogy & Families',
    })


@require_role(['memorial_admin', 'content_admin'])
def memorial_dashboard(request):
    return render(request, 'dashboard/memorial_dashboard.html', {
        'memorials': MemorialRecord.objects.select_related('person', 'person__clan').order_by('-created_at')[:25],
        'total':     MemorialRecord.objects.count(),
        'featured':  MemorialRecord.objects.filter(is_featured=True).count(),
        'page_title': 'Memorial Records',
    })


@require_role(['cultural_admin', 'content_admin'])
def cultural_dashboard(request):
    from apps.cultural.models import RECORD_TYPE_CHOICES
    type_counts = {label: CulturalRecord.objects.filter(record_type=val).count() for val, label in RECORD_TYPE_CHOICES}
    return render(request, 'dashboard/cultural_dashboard.html', {
        'records':     CulturalRecord.objects.select_related('clan').order_by('-created_at')[:25],
        'total':       CulturalRecord.objects.count(),
        'verified':    CulturalRecord.objects.filter(is_verified=True).count(),
        'type_counts': type_counts,
        'page_title':  'Cultural Archive',
    })


@require_role(['elder_admin', 'cultural_admin', 'content_admin'])
def elder_dashboard(request):
    return render(request, 'dashboard/elder_dashboard.html', {
        'interviews':  ElderInterview.objects.select_related('clan').order_by('-interview_date')[:25],
        'total':       ElderInterview.objects.count(),
        'published':   ElderInterview.objects.filter(is_published=True).count(),
        'unpublished': ElderInterview.objects.filter(is_published=False).count(),
        'with_audio':  ElderInterview.objects.exclude(audio_file='').count(),
        'with_video':  ElderInterview.objects.exclude(video_url='').count(),
        'page_title':  'Elder Interviews',
    })


@require_role(['achievement_admin', 'content_admin'])
def achievement_dashboard(request):
    from apps.achievements.models import CATEGORY_CHOICES
    cat_counts = {label: Achievement.objects.filter(category=val).count() for val, label in CATEGORY_CHOICES}
    return render(request, 'dashboard/achievement_dashboard.html', {
        'achievements': Achievement.objects.select_related('clan').order_by('-created_at')[:25],
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
    if request.method == 'POST' and form.is_valid():
        clan = form.save()
        media_formset = ClanMediaFormSet(request.POST, request.FILES, instance=clan)
        if media_formset.is_valid():
            media_formset.save()
        messages.success(request, f'✅ {clan.name} Clan created successfully.')
        return redirect('dashboard:clan_dashboard')
    media_formset = ClanMediaFormSet(request.POST or None, request.FILES or None)
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
        delete_url=reverse('dashboard:clan_delete', args=[pk]),
        media_formset=media_formset, media_title='Photos, Documents & Media for this Clan',
        media_help='Upload photos, PDFs, audio, or video for any section above — tag each item to the relevant section (history, geography, boma, culture, leadership, etc.).',
        page_title=f'Edit {clan.name} Clan')


@require_superadmin
def clan_delete(request, pk):
    clan = get_object_or_404(Clan, pk=pk)
    if request.method == 'POST':
        name = clan.name
        clan.delete()
        messages.success(request, f'🗑️ {name} Clan deleted.')
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
    if request.method == 'POST' and form.is_valid():
        person = form.save()
        media_formset = PersonMediaFormSet(request.POST, request.FILES, instance=person)
        if media_formset.is_valid():
            media_formset.save()
        messages.success(request, f'✅ {person.full_name} added to the archive.')
        return redirect('dashboard:genealogy_dashboard')
    media_formset = PersonMediaFormSet(request.POST or None, request.FILES or None)
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
        delete_url=reverse('dashboard:person_delete', args=[pk]),
        media_formset=media_formset, media_title='Photos, Documents & Media for this Person',
        media_help='Upload profile photos, certificates, PDFs, audio, or video related to this person.',
        page_title=f'Edit {person.full_name}')


@require_superadmin
def person_delete(request, pk):
    person = get_object_or_404(Person, pk=pk)
    if request.method == 'POST':
        name = person.full_name
        person.delete()
        messages.success(request, f'🗑️ {name} deleted.')
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
        delete_url=reverse('dashboard:family_delete', args=[pk]),
        page_title=f'Edit {family.name}')


@require_superadmin
def family_delete(request, pk):
    family = get_object_or_404(Family, pk=pk)
    if request.method == 'POST':
        name = family.name
        family.delete()
        messages.success(request, f'🗑️ {name} deleted.')
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
        delete_url=reverse('dashboard:memorial_delete', args=[pk]),
        page_title=f'Edit Memorial: {mem.person.full_name}')


@require_superadmin
def memorial_delete(request, pk):
    mem = get_object_or_404(MemorialRecord, pk=pk)
    if request.method == 'POST':
        name = mem.person.full_name
        mem.delete()
        messages.success(request, f'🗑️ Memorial for {name} deleted.')
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
        delete_url=reverse('dashboard:elder_delete', args=[pk]),
        page_title=f'Edit Interview: {iv.elder_name}')


@require_superadmin
def elder_delete(request, pk):
    iv = get_object_or_404(ElderInterview, pk=pk)
    if request.method == 'POST':
        name = iv.elder_name
        iv.delete()
        messages.success(request, f'🗑️ Interview with {name} deleted.')
    return redirect('dashboard:elder_dashboard')


# ── SUBMISSION REVIEW ─────────────────────────────────

@require_dashboard
def submission_list(request):
    subs = Submission.objects.order_by('-created_at')
    status_filter = request.GET.get('status', '')
    if status_filter:
        subs = subs.filter(status=status_filter)
    return render(request, 'dashboard/submissions.html', {
        'submissions':     subs[:50],
        'status_filter':   status_filter,
        'pending_count':   Submission.objects.filter(status='pending').count(),
        'page_title':      'Submission Review',
    })


@require_dashboard
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


# ── ACCOUNT MANAGEMENT ────────────────────────────────

@require_superadmin
def manage_accounts(request):
    return render(request, 'dashboard/accounts.html', {
        'admins': AdminProfile.objects.select_related('user', 'assigned_by').order_by('-created_at'),
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
        form.save()
        profile.assign_permissions()
        messages.success(request, '✅ Account updated.')
        return redirect('dashboard:accounts')
    return _render_form(request, form,
        title=f'Edit Account: {profile.user.get_full_name() or profile.user.username}',
        cancel_url=reverse('dashboard:accounts'),
        full_fields=['notes'], obj=profile,
        delete_url=reverse('dashboard:deactivate_account', args=[pk]),
        page_title='Edit Admin Account')


@require_superadmin
def deactivate_account(request, pk):
    profile = get_object_or_404(AdminProfile, pk=pk)
    if request.method == 'POST':
        profile.is_active = False; profile.save()
        profile.user.is_active = False; profile.user.save()
        messages.success(request, f'{profile.user.get_full_name()} deactivated.')
    return redirect('dashboard:accounts')


@require_superadmin
def reactivate_account(request, pk):
    profile = get_object_or_404(AdminProfile, pk=pk)
    if request.method == 'POST':
        profile.is_active = True; profile.save()
        profile.user.is_active = True; profile.user.save()
        messages.success(request, f'{profile.user.get_full_name()} reactivated.')
    return redirect('dashboard:accounts')