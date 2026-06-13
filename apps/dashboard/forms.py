from django import forms
from django.contrib.auth.models import User
from apps.clans.models import Clan, ClanChief, ClanEvent
from apps.genealogy.models import Person, Family
from apps.memorial.models import MemorialRecord
from apps.achievements.models import Achievement, CATEGORY_CHOICES
from apps.marriages.models import Marriage
from apps.cultural.models import CulturalRecord, RECORD_TYPE_CHOICES
from apps.elders.models import ElderInterview
from apps.submissions.models import Submission
from apps.core.models import PAYAM_CHOICES
from .models import AdminProfile, ROLE_CHOICES
from django.forms import inlineformset_factory
from apps.clans.models import ClanMedia, CLAN_SECTION_CHOICES
from apps.genealogy.models import PersonMedia

# ── Widget shorthand ───────────────────────────
FC  = lambda ph='', rows=0: forms.TextInput(attrs={'class':'form-control','placeholder':ph}) if not rows else forms.Textarea(attrs={'class':'form-control','rows':rows,'placeholder':ph})
TA  = lambda rows=5, ph='': forms.Textarea(attrs={'class':'form-control','rows':rows,'placeholder':ph})
SEL = lambda: forms.Select(attrs={'class':'form-select'})
CHK = lambda: forms.CheckboxInput(attrs={'class':'form-check-input'})
FIL = lambda: forms.FileInput(attrs={'class':'form-control'})
DAT = lambda: forms.DateInput(attrs={'class':'form-control','type':'date'})
NUM = lambda ph='': forms.NumberInput(attrs={'class':'form-control','placeholder':ph})

# ── Full-width field names (used in template) ──
CLAN_FULL     = ['tagline','description','origin_story','migration_history','territorial_notes','cultural_practices','traditional_beliefs','historical_events','sub_clans','allied_clans']
PERSON_FULL   = ['biography','contributions','education','other_names']
FAMILY_FULL   = ['description']
MEMORIAL_FULL = ['tribute','survived_by','epitaph']
ACHIEVE_FULL  = ['title','description']
MARRIAGE_FULL = ['children_names','notes']
CULTURAL_FULL = ['content','translation','context']
ELDER_FULL    = ['summary','transcript','topics_covered']


# ═══════════════════════════════════════════════
# ADMIN ACCOUNT FORMS
# ═══════════════════════════════════════════════

class CreateAdminForm(forms.Form):
    first_name  = forms.CharField(max_length=100, widget=FC('First name'))
    last_name   = forms.CharField(max_length=100, widget=FC('Last name'))
    email       = forms.EmailField(widget=forms.EmailInput(attrs={'class':'form-control','placeholder':'Email address'}))
    username    = forms.CharField(max_length=150, widget=FC('Username (for login)'))
    password    = forms.CharField(widget=forms.PasswordInput(attrs={'class':'form-control','placeholder':'Set a strong password'}))
    role        = forms.ChoiceField(choices=ROLE_CHOICES, widget=SEL())
    phone       = forms.CharField(max_length=50, required=False, widget=FC('Phone number (optional)'))
    notes       = forms.CharField(required=False, widget=TA(3,'Notes about this administrator'))

    def clean_username(self):
        u = self.cleaned_data['username']
        if User.objects.filter(username=u).exists():
            raise forms.ValidationError('This username is already taken.')
        return u

    def clean_email(self):
        e = self.cleaned_data['email']
        if User.objects.filter(email=e).exists():
            raise forms.ValidationError('An account with this email already exists.')
        return e


class EditAdminForm(forms.ModelForm):
    first_name = forms.CharField(max_length=100, widget=FC('First name'))
    last_name  = forms.CharField(max_length=100, widget=FC('Last name'))
    email      = forms.EmailField(widget=forms.EmailInput(attrs={'class':'form-control'}))

    class Meta:
        model   = AdminProfile
        fields  = ['role','phone','notes','is_active']
        widgets = {'role':SEL(), 'phone':FC(), 'notes':TA(3), 'is_active':CHK()}


# ═══════════════════════════════════════════════
# CLAN FORMS
# ═══════════════════════════════════════════════

class ClanForm(forms.ModelForm):
    class Meta:
        model  = Clan
        fields = ['name','payam','tagline','description','origin_story',
                  'migration_history','territorial_notes','cultural_practices',
                  'traditional_beliefs','historical_events','sub_clans',
                  'allied_clans','is_verified','is_featured']
        widgets = {
            'name':                FC('e.g. Gumbo'),
            'payam':               SEL(),
            'tagline':             FC('One-sentence description shown on cards'),
            'description':         TA(4,'General overview of the clan...'),
            'origin_story':        TA(5,'Where does this clan come from? What is their founding story?'),
            'migration_history':   TA(4,'Migration routes and settlement history...'),
            'territorial_notes':   TA(4,'Territorial and land history...'),
            'cultural_practices':  TA(4,'Cultural practices, ceremonies, and customs...'),
            'traditional_beliefs': TA(4,'Spiritual and traditional beliefs...'),
            'historical_events':   TA(4,'Important historical events involving this clan...'),
            'sub_clans':           FC('Sub-clans or branches (comma-separated)'),
            'allied_clans':        forms.CheckboxSelectMultiple(attrs={'class':'list-unstyled'}),
            'is_verified':         CHK(),
            'is_featured':         CHK(),
        }


class ClanChiefForm(forms.ModelForm):
    class Meta:
        model  = ClanChief
        fields = ['clan','name','title','start_year','end_year','order','notes']
        widgets = {
            'clan':       SEL(),
            'name':       FC('Full name of the chief or elder'),
            'title':      FC('e.g. Chief, Paramount Chief, Elder'),
            'start_year': FC('e.g. 1955'),
            'end_year':   FC('e.g. 1991 or leave blank if current'),
            'order':      NUM('Display order (0 = earliest)'),
            'notes':      TA(3,'Additional notes about this leader...'),
        }


class ClanEventForm(forms.ModelForm):
    class Meta:
        model  = ClanEvent
        fields = ['clan','title','year','description','significance']
        widgets = {
            'clan':         SEL(),
            'title':        FC('Title of the historical event'),
            'year':         FC('e.g. 1924 or approx. early 1900s'),
            'description':  TA(5,'Describe what happened...'),
            'significance': FC('Why was this event significant?'),
        }


# ═══════════════════════════════════════════════
# GENEALOGY FORMS
# ═══════════════════════════════════════════════

# ── Full-width field names (updated) ──
PERSON_FULL   = ['biography', 'contributions', 'hobbies', 'skills_talents',
                 'other_names', 'address']

class PersonForm(forms.ModelForm):
    class Meta:
        model  = Person
        fields = [
            # Identity
            'first_name', 'middle_name', 'last_name', 'other_names', 'gender',
            # Heritage
            'clan', 'family', 'payam',
            # Parents
            'father', 'mother',
            # Birth & death
            'birth_year', 'birth_date', 'birth_place',
            'is_deceased', 'death_year', 'death_date', 'death_place',
            # Contact & location
            'phone', 'email_contact', 'address', 'current_residence',
            # Profile
            'photo', 'biography', 'occupation',
            'hobbies', 'skills_talents', 'languages_spoken', 'religion',
            # Contributions
            'contributions',
            # Document
            'profile_pdf',
            # Status
            'is_verified', 'is_elder', 'submitted_by',
        ]
        widgets = {
            'first_name':        FC('First name'),
            'middle_name':       FC('Middle name (optional)'),
            'last_name':         FC('Family / last name'),
            'other_names':       FC('Traditional or other known names'),
            'gender':            SEL(),
            'clan':              SEL(),
            'family':            SEL(),
            'payam':             SEL(),
            'father':            SEL(),
            'mother':            SEL(),
            'birth_year':        FC('e.g. 1945 or approx. 1940s'),
            'birth_date':        DAT(),
            'birth_place':       FC('Village or town of birth'),
            'is_deceased':       CHK(),
            'death_year':        FC('e.g. 2018'),
            'death_date':        DAT(),
            'death_place':       FC('Place of passing'),
            'phone':             FC('e.g. +211 912 345 678'),
            'email_contact':     forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email address (optional)'}),
            'address':           TA(2, 'Physical address'),
            'current_residence': FC('City / country of current residence'),
            'photo':             FIL(),
            'biography':         TA(5, 'Life story — background, upbringing, and history…'),
            'occupation':        FC('e.g. Farmer, Teacher, Nurse, Engineer'),
            'hobbies':           TA(3, 'Hobbies and personal interests…'),
            'skills_talents':    TA(3, 'Skills, talents, and gifts…'),
            'languages_spoken':  FC('e.g. Pojulu, Arabic, English, Swahili'),
            'religion':          FC('e.g. Catholic, Anglican, Evangelical'),
            'contributions':     TA(3, 'Notable contributions to the community…'),
            'profile_pdf':       FIL(),
            'is_verified':       CHK(),
            'is_elder':          CHK(),
            'submitted_by':      FC('Name of person who submitted this record'),
        }


class FamilyForm(forms.ModelForm):
    class Meta:
        model  = Family
        fields = ['name','clan','payam','origin_village','description','is_verified']
        widgets = {
            'name':           FC('e.g. Ladu Family'),
            'clan':           SEL(),
            'payam':          SEL(),
            'origin_village': FC('Original village or settlement'),
            'description':    TA(4,'History and background of this family...'),
            'is_verified':    CHK(),
        }


# ═══════════════════════════════════════════════
# MEMORIAL FORM
# ═══════════════════════════════════════════════

class MemorialRecordForm(forms.ModelForm):
    class Meta:
        model  = MemorialRecord
        fields = ['person','tribute','survived_by','burial_place','epitaph','is_featured','submitted_by']
        widgets = {
            'person':       SEL(),
            'tribute':      TA(6,'Full tribute — life story, legacy, community role...'),
            'survived_by':  TA(3,'Names of surviving family members...'),
            'burial_place': FC('Village or cemetery'),
            'epitaph':      FC('Short memorable quote or epitaph (optional)'),
            'is_featured':  CHK(),
            'submitted_by': FC('Name of person who submitted this record'),
        }


# ═══════════════════════════════════════════════
# ACHIEVEMENT FORM
# ═══════════════════════════════════════════════

class AchievementForm(forms.ModelForm):
    class Meta:
        model  = Achievement
        fields = ['person_name','person','clan','category','title','description',
                  'year','source','is_verified','is_featured']
        widgets = {
            'person_name': FC('Full name of the person being honoured'),
            'person':      SEL(),
            'clan':        SEL(),
            'category':    SEL(),
            'title':       FC('One-line achievement title'),
            'description': TA(5,'Describe the achievement in full...'),
            'year':        FC('e.g. 2018'),
            'source':      FC('Source or reference for this achievement'),
            'is_verified': CHK(),
            'is_featured': CHK(),
        }


# ═══════════════════════════════════════════════
# MARRIAGE FORM
# ═══════════════════════════════════════════════

class MarriageForm(forms.ModelForm):
    class Meta:
        model  = Marriage
        fields = ['husband','husband_name','husband_clan','husband_community',
                  'wife','wife_name','wife_clan','wife_community',
                  'year','place','payam','children_names','notes','is_verified']
        widgets = {
            'husband':           SEL(),
            'husband_name':      FC('Husband full name (if not in archive)'),
            'husband_clan':      SEL(),
            'husband_community': FC('Community if non-Pojulu'),
            'wife':              SEL(),
            'wife_name':         FC('Wife full name (if not in archive)'),
            'wife_clan':         SEL(),
            'wife_community':    FC('Community if non-Pojulu'),
            'year':              FC('e.g. 1972'),
            'place':             FC('Village or town'),
            'payam':             FC('Payam or area'),
            'children_names':    TA(3,'Names of children from this union (comma-separated)...'),
            'notes':             TA(3,'Additional notes...'),
            'is_verified':       CHK(),
        }


# ═══════════════════════════════════════════════
# CULTURAL RECORD FORM
# ═══════════════════════════════════════════════

class CulturalRecordForm(forms.ModelForm):
    class Meta:
        model  = CulturalRecord
        fields = ['title','record_type','clan','language','content','translation',
                  'context','performers','audio_file','video_url','image',
                  'source','is_verified','is_featured']
        widgets = {
            'title':       FC('Title of this cultural record'),
            'record_type': SEL(),
            'clan':        SEL(),
            'language':    FC('e.g. Pojulu, English, Arabic'),
            'content':     TA(6,'Full text — lyrics, proverb, story, description...'),
            'translation': TA(4,'English translation if in Pojulu language...'),
            'context':     TA(3,'When and how this is used or performed...'),
            'performers':  FC('Who traditionally performs or recites this'),
            'audio_file':  FIL(),
            'video_url':   forms.URLInput(attrs={'class':'form-control','placeholder':'YouTube or Vimeo URL'}),
            'image':       FIL(),
            'source':      FC('Source: elder name, interview date, document reference'),
            'is_verified': CHK(),
            'is_featured': CHK(),
        }


# ═══════════════════════════════════════════════
# ELDER INTERVIEW FORM
# ═══════════════════════════════════════════════

class ElderInterviewForm(forms.ModelForm):
    class Meta:
        model  = ElderInterview
        fields = ['elder_name','elder_person','clan','payam','approximate_age',
                  'interview_date','interview_location','interviewer','language',
                  'summary','transcript','topics_covered',
                  'audio_file','video_file','video_url','photo_of_elder',
                  'clans_mentioned','is_published','is_featured']
        widgets = {
            'elder_name':         FC('Full name of the elder'),
            'elder_person':       SEL(),
            'clan':               SEL(),
            'payam':              FC('e.g. Lainya Centre, Kupera, Kenyi'),
            'approximate_age':    NUM('Approximate age at time of interview'),
            'interview_date':     DAT(),
            'interview_location': FC('Village or town where interview took place'),
            'interviewer':        FC('Full name of the interviewer'),
            'language':           FC('e.g. Pojulu / English'),
            'summary':            TA(5,'Summary of topics covered and key knowledge shared...'),
            'transcript':         TA(8,'Full transcript of the interview...'),
            'topics_covered':     FC('Comma-separated topics: genealogy, ceremonies, history...'),
            'audio_file':         FIL(),
            'video_file':         FIL(),
            'video_url':          forms.URLInput(attrs={'class':'form-control','placeholder':'YouTube or Vimeo link'}),
            'photo_of_elder':     FIL(),
            'clans_mentioned':    forms.CheckboxSelectMultiple(attrs={'class':'list-unstyled'}),
            'is_published':       CHK(),
            'is_featured':        CHK(),
        }


# ═══════════════════════════════════════════════
# SUBMISSION REVIEW FORM
# ═══════════════════════════════════════════════

class SubmissionReviewForm(forms.ModelForm):
    class Meta:
        model  = Submission
        fields = ['status','reviewer_notes']
        widgets = {
            'status':         SEL(),
            'reviewer_notes': TA(4,'Internal notes — visible to staff only...'),
        }

        # ═══════════════════════════════════════════════
# MEDIA FORMSETS — section-tagged photo/document/video/audio uploads
# ═══════════════════════════════════════════════

ClanMediaFormSet = inlineformset_factory(
    Clan, ClanMedia,
    fields=['section', 'media_type', 'title', 'file', 'video_url', 'caption', 'date_taken'],
    extra=3, can_delete=True,
    widgets={
        'section':    SEL(),
        'media_type': SEL(),
        'title':      FC('e.g. "Lainya Centre market in 1985"'),
        'file':       FIL(),
        'video_url':  forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'YouTube/Vimeo link (optional)'}),
        'caption':    TA(2, 'Caption or description of this photo/document...'),
        'date_taken': FC('Date or approximate year'),
    }
)

PersonMediaFormSet = inlineformset_factory(
    Person, PersonMedia,
    fields=['media_type', 'title', 'file', 'video_url', 'caption', 'date_taken', 'is_profile_photo'],
    extra=3, can_delete=True,
    widgets={
        'media_type':       SEL(),
        'title':            FC('e.g. "Graduation photo, 1998"'),
        'file':             FIL(),
        'video_url':        forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'YouTube/Vimeo link (optional)'}),
        'caption':          TA(2, 'Caption or description...'),
        'date_taken':       FC('Date or approximate year'),
        'is_profile_photo': CHK(),
    }
)