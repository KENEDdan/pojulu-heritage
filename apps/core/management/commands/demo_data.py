"""Fill the local database with mock data, and remove it again.

    py manage.py demo_data            # create the demo data
    py manage.py demo_data --delete   # remove exactly what was created
    py manage.py demo_data --extend   # add histories, landmarks, maps and evidence
                                      # to demo data created by an older version

Every row and file this command creates is written to a manifest
(MEDIA_ROOT/.demo_seed_manifest.json), so --delete removes only demo records
and never touches real data, even when both are present. The names, places
and stories are invented for testing the site; they are not real records.
"""
import io
import json
import random
from datetime import date, datetime, timedelta
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import models, transaction
from django.utils import timezone

def manifest_path():
    return Path(settings.MEDIA_ROOT) / '.demo_seed_manifest.json'
TAG = 'demo seed'
STAFF_PASSWORD = 'Heritage-Demo-2026'
FAMILY_PASSWORD = 'Family-Demo-2026'
WILL_PASSPHRASE = 'demo will passphrase'

MALE = ['Lado', 'Loku', 'Wani', 'Kenyi', 'Pitia', 'Gore', 'Modi', 'Jada', 'Tombe', 'Lemi',
        'Jube', 'Lomeri', 'Swaka', 'Taban', 'Lokuji', 'Yugusuk', 'Ladu', 'Mogga', 'Soma', 'Legge',
        'Ali', 'Duku', 'Lubang', 'Kwaje', 'Wurube', 'Kosta', 'Moses', 'Emmanuel', 'Samuel', 'David']
FEMALE = ['Poni', 'Kiden', 'Gune', 'Jore', 'Yeno', 'Sitima', 'Jokudu', 'Ropani', 'Mere', 'Kide',
          'Kaku', 'Lilian', 'Juan', 'Nyoka', 'Konga', 'Yangi', 'Tabu', 'Mary', 'Grace', 'Rose',
          'Esther', 'Joice', 'Agnes', 'Night', 'Viola', 'Susan', 'Hellen', 'Betty', 'Ruth', 'Sarah']
PALETTE = [('#1B5E20', '#A5D6A7'), ('#4E342E', '#D7CCC8'), ('#BF360C', '#FFCC80'),
           ('#0D47A1', '#90CAF9'), ('#4A148C', '#CE93D8'), ('#33691E', '#DCE775')]

CLANS = [
    dict(name='Lojuba', payam='kupera', featured=True,
         tagline='Keepers of the river crossings',
         rivers='Kupera stream and the seasonal Lojuba wetlands',
         activities='Sorghum and groundnut farming, fishing in the wet season, honey collection',
         sub='Lojuba-Kaya, Lojuba-Ngulu'),
    dict(name='Mogiri', payam='lainya_centre', featured=True,
         tagline='People of the granite hills',
         rivers='Springs below Mogiri hill feed the Lainya stream',
         activities='Cattle and goat keeping, cassava farming, blacksmithing',
         sub='Mogiri-Lo, Mogiri-Tore'),
    dict(name='Kenyiyo', payam='kenyi', featured=True,
         tagline='Guardians of the old market road',
         rivers='Kenyi river and its tributaries',
         activities='Trade at Kenyi market, maize and simsim farming, charcoal',
         sub='Kenyiyo-Dongo'),
    dict(name='Wujiyo', payam='wuji', featured=False,
         tagline='The forest clan',
         rivers='Wuji forest streams',
         activities='Hunting (historically), timber, teak plantations, beekeeping',
         sub='Wujiyo-Kulu, Wujiyo-Mere, Wujiyo-Lo'),
    dict(name='Mukayo', payam='mukaya', featured=False,
         tagline='Builders of the first schools',
         rivers='Mukaya river',
         activities='Mixed farming, teaching, small trade',
         sub=''),
    # Unverified on purpose: a draft clan that must not appear publicly.
    dict(name='Wondurubo', payam='wonduruba', featured=False, verified=False,
         tagline='Draft record awaiting verification',
         rivers='', activities='', sub=''),
]

ROLES = ['clan_admin', 'genealogy_admin', 'memorial_admin', 'cultural_admin',
         'elder_admin', 'achievement_admin', 'content_admin']


def picture(text, seed, size=(1200, 800)):
    """A simple generated JPEG (gradient + initials) so pages show real images."""
    from PIL import Image, ImageDraw, ImageFont
    dark, light = PALETTE[seed % len(PALETTE)]
    mask = Image.linear_gradient('L').resize(size)
    img = Image.composite(Image.new('RGB', size, light), Image.new('RGB', size, dark), mask)
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default(size=size[1] // 3)
    box = draw.textbbox((0, 0), text, font=font)
    xy = ((size[0] - (box[2] - box[0])) / 2 - box[0], (size[1] - (box[3] - box[1])) / 2 - box[1])
    draw.text(xy, text, fill='white', font=font)
    buf = io.BytesIO()
    img.save(buf, 'JPEG', quality=85)
    return ContentFile(buf.getvalue(), name='demo.jpg')


def initials(text):
    return ''.join(w[0] for w in text.split()[:2]).upper()


class Command(BaseCommand):
    help = 'Create mock data for local testing (or remove it with --delete).'

    def add_arguments(self, parser):
        parser.add_argument('--delete', action='store_true', help='Remove all demo data.')
        parser.add_argument('--extend', action='store_true',
                            help='Add written histories, landmarks, maps and evidence to existing demo data.')

    def handle(self, *args, **opts):
        if opts['delete']:
            return self.delete()
        if opts['extend']:
            return self.extend()
        if manifest_path().exists():
            raise CommandError('Demo data already exists. Run "demo_data --delete" first.')
        self.created = []
        self.files = []
        self.rnd = random.Random(2026)
        try:
            with transaction.atomic():
                self.seed()
        except Exception:
            # The rows rolled back; remove any image files already written.
            for f in self.files:
                f.storage.delete(f.name)
            raise
        manifest_path().parent.mkdir(parents=True, exist_ok=True)
        manifest_path().write_text(json.dumps(self.created, indent=1))
        self.report()

    # ── helpers ───────────────────────────────────────────────────────────
    def make(self, model, **kw):
        obj = model.objects.create(**kw)
        self.created.append([obj._meta.label, obj.pk])
        for f in obj._meta.fields:
            if isinstance(f, models.FileField) and getattr(obj, f.attname):
                self.files.append(getattr(obj, f.attname))
        return obj

    def pick(self, seq):
        return self.rnd.choice(seq)

    def demo(self, label):
        """Demo rows of one model, from the manifest, in creation order."""
        model = apps.get_model(label)
        pks = [pk for lab, pk in self.created if lab == label]
        manager = getattr(model, 'all_objects', model._default_manager)
        by_pk = manager.in_bulk(pks)
        return [by_pk[pk] for pk in pks if pk in by_pk]

    def attach(self, record, title, caption='', is_public=True, kind='photo', seed=0, text=None):
        from django.contrib.contenttypes.models import ContentType
        from apps.core.models import Attachment
        return self.make(Attachment, content_type=ContentType.objects.get_for_model(record), object_id=record.pk,
                         kind=kind, title=title, caption=caption, is_public=is_public,
                         source='Demo seed', date_taken=str(self.rnd.randint(1950, 2024)),
                         file=picture(text or initials(title), seed))

    def extend(self):
        if not manifest_path().exists():
            raise CommandError('No demo data found. Run "demo_data" first.')
        self.created = json.loads(manifest_path().read_text())
        if any(label == 'clans.ClanLandmark' for label, _ in self.created):
            raise CommandError('Demo data already has landmarks and histories.')
        self.files = []
        self.rnd = random.Random(2027)
        try:
            with transaction.atomic():
                self.seed_heritage()
        except Exception:
            for f in self.files:
                f.storage.delete(f.name)
            raise
        manifest_path().write_text(json.dumps(self.created, indent=1))
        self.stdout.write(self.style.SUCCESS('Added written histories, chapters, chief biographies, '
                                             'territory maps, landmarks and photos/evidence to the demo data.'))

    # ── seeding ───────────────────────────────────────────────────────────
    def seed(self):
        from apps.achievements.models import Achievement
        from apps.clans.models import Clan, ClanBoma, ClanChief, ClanEvent
        from apps.core.models import Announcement
        from apps.cultural.models import CulturalRecord
        from apps.dashboard.models import AdminProfile
        from apps.elders.models import ElderInterview
        from apps.genealogy.models import Family, Person, PersonCareer, PersonEducation
        from apps.marriages.models import Marriage
        from apps.memorial.models import MemorialRecord
        from apps.news.models import NewsPost
        from apps.wills.models import FamilyAccount, Will

        su = User.objects.filter(is_superuser=True).order_by('pk').first()
        self.stats = {}

        # Staff accounts, one per role, plus a deactivated one.
        for role in ROLES + ['deactivated']:
            username = f'demo_{role.replace("_admin", "")}'
            user = User.objects.create_user(
                username=username, password=STAFF_PASSWORD, email=f'{username}@example.org',
                first_name='Demo', last_name=role.replace('_', ' ').title(), is_staff=True)
            self.created.append(['auth.User', user.pk])
            profile = self.make(AdminProfile, user=user, assigned_by=su,
                                role='clan_admin' if role == 'deactivated' else role,
                                is_active=role != 'deactivated', notes=TAG)
            profile.assign_permissions()

        # Clans with chiefs, events and bomas.
        clans = []
        for i, c in enumerate(CLANS):
            name = c['name']
            clan = self.make(
                Clan, name=name, payam=c['payam'], tagline=c['tagline'],
                is_verified=c.get('verified', True), is_featured=c['featured'],
                description=(f'The {name} clan is one of the Pojulu communities of Lainya County, '
                             f'Central Equatoria. Its people are known for {c["activities"].split(",")[0].lower() or "farming"} '
                             f'and for the oral histories kept by its elders.'),
                origin_story=(f'Elders say the {name} people descend from a hunter who followed a wounded '
                              f'antelope to the place where the clan now lives, and settled there when '
                              f'the rains came early that year.'),
                migration_history=('Families moved south during the dry seasons of the early 1900s, and many '
                                   'returned after the 2005 peace agreement. Some households remain in Uganda and Kenya.'),
                cultural_practices='Harvest dances, rain-making rites led by the clan elder, and naming ceremonies on the seventh day after birth.',
                traditional_beliefs='Respect for ancestral spirits at the family shrine; certain trees near the homestead are never cut.',
                historical_events='The clan hosted inter-clan peace talks in 1972 and rebuilt its school in 2008.',
                population_estimate=f'{self.rnd.randint(3, 18)},000 (estimate)',
                border_north='Neighbouring Pojulu clan lands', border_south='Seasonal river',
                border_east='Old market road', border_west='Hills and forest reserve',
                rivers=c['rivers'], landscape='Rolling savannah with granite outcrops and gallery forest along the streams.',
                main_activities=c['activities'],
                infrastructure='One primary school, a health post, two churches and a weekly market.',
                sub_clans=c['sub'])
            clans.append(clan)
            if not c.get('verified', True):
                continue
            for n, (title, start, end) in enumerate([('Chief', '1948', '1979'), ('Chief', '1979', '')]):
                self.make(ClanChief, clan=clan, name=f'{self.pick(MALE)} {self.pick(MALE)}', title=title,
                          start_year=start, end_year=end, order=n,
                          notes='Remembered for settling land disputes and keeping the peace between families.',
                          photo=picture(initials(name), i + n) if n == 1 else None)
            for year, title in [('1955', 'The great flood'), ('2008', 'School rebuilt by the community')]:
                self.make(ClanEvent, clan=clan, title=title, year=year,
                          description=f'{title} is still talked about by the {name} elders.',
                          significance='Shaped where families live today.')
            for n, boma in enumerate([f'{name} North', f'{name} South']):
                self.make(ClanBoma, clan=clan, name=boma, order=n, year_established=str(1930 + 10 * n),
                          history=f'{boma} grew around a well dug by the first families.',
                          current_leader=f'{self.pick(MALE)} {self.pick(MALE)}',
                          population=f'{self.rnd.randint(800, 4000)} (estimate)',
                          main_activities=c['activities'],
                          location_description='Along the road between the market and the river.')
        live = clans[:5]
        live[0].allied_clans.add(live[1], live[2])
        live[3].allied_clans.add(live[4])

        # Families and four generations of people.
        families, elders, deceased, gen2_all, gen3_all = [], [], [], [], []
        surnames = ['Lado', 'Wani', 'Pitia', 'Modi', 'Tombe', 'Lemi', 'Kenyi', 'Gore']
        for i, surname in enumerate(surnames):
            clan = live[i % len(live)]
            fam = self.make(Family, name=f'{surname} Family', clan=clan, payam=clan.payam,
                            origin_village=f'{clan.name} {self.pick(["North", "South"])}',
                            description=f'Descendants of {surname} of the {clan.name} clan.',
                            is_verified=True)
            families.append(fam)

            def person(first, last, gender, born, **kw):
                kw.setdefault('is_verified', True)
                return self.make(Person, first_name=first, last_name=last, gender=gender,
                                 clan=fam.clan, family=fam, payam=fam.payam, birth_year=str(born),
                                 birth_place=f'{fam.clan.name}, Lainya County', submitted_by=TAG,
                                 languages_spoken='Pojulu, Arabic, English', religion='Christian', **kw)

            b1 = self.rnd.randint(1915, 1930)
            patriarch = person(self.pick(MALE), surname, 'M', b1, is_deceased=True,
                               death_year=str(b1 + self.rnd.randint(55, 80)),
                               death_place='Lainya', occupation='Farmer and clan elder',
                               biography=f'Founder of the {surname} family homestead. He kept cattle and taught his children the clan songs.',
                               photo=picture(surname[:2].upper(), i))
            matriarch_dead = i % 3 == 0
            matriarch = person(self.pick(FEMALE), self.pick(MALE), 'F', b1 + self.rnd.randint(3, 8),
                               is_deceased=matriarch_dead,
                               death_year=str(b1 + 85) if matriarch_dead else '',
                               is_elder=not matriarch_dead, occupation='Farmer, midwife',
                               biography='Known across the payam as a midwife and a singer of harvest songs.')
            self.make(Marriage, husband=patriarch, wife=matriarch, year=str(b1 + 22),
                      place=fam.origin_village, payam=fam.payam, is_verified=True,
                      notes='Traditional marriage with bride wealth in cattle.')
            deceased.append(patriarch)
            (deceased if matriarch_dead else elders).append(matriarch)

            gen2 = []
            for k in range(3):
                g = 'M' if k != 1 else 'F'
                gen2.append(person(self.pick(MALE if g == 'M' else FEMALE), patriarch.first_name, g,
                                   b1 + 25 + 4 * k, father=patriarch, mother=matriarch,
                                   occupation=self.pick(['Teacher', 'Farmer', 'Nurse', 'Pastor', 'Trader']),
                                   current_residence=self.pick(['Lainya', 'Juba', 'Yei', 'Kampala'])))
            gen2_all += gen2
            heir = gen2[0]
            spouse_clan = live[(i + 1) % len(live)]
            wife = self.make(Person, first_name=self.pick(FEMALE), last_name=self.pick(MALE), gender='F',
                             clan=spouse_clan, payam=spouse_clan.payam, birth_year=str(int(heir.birth_year) + 4),
                             is_verified=True, submitted_by=TAG, occupation='Tailor')
            self.make(Marriage, husband=heir, wife=wife, year=str(int(heir.birth_year) + 26),
                      place='Lainya', payam=fam.payam, is_verified=True,
                      husband_clan=fam.clan, wife_clan=spouse_clan)

            gen3 = []
            for k in range(3):
                g = 'F' if k == 1 else 'M'
                born = int(heir.birth_year) + 28 + 3 * k
                gen3.append(person(self.pick(MALE if g == 'M' else FEMALE), heir.first_name, g, born,
                                   father=heir, mother=wife,
                                   birth_date=date(born, self.rnd.randint(1, 12), self.rnd.randint(1, 28)),
                                   occupation=self.pick(['Civil engineer', 'Doctor', 'Accountant', 'Lecturer',
                                                         'Software developer', 'Agronomist', 'Lawyer']),
                                   current_residence=self.pick(['Juba', 'Nairobi', 'Kampala', 'Melbourne', 'Calgary']),
                                   phone=f'+211 9{self.rnd.randint(10, 99)} {self.rnd.randint(100000, 999999)}',
                                   email_contact=f'demo{i}{k}@example.org',
                                   address='Hai Malakal, Juba (demo address)',
                                   hobbies='Football, choir, reading',
                                   photo=picture(initials(f'{heir.first_name} {k}'), i + k + 1) if k == 0 else None))
            gen3_all += gen3
            for k in range(2):
                g = 'M' if k == 0 else 'F'
                person(self.pick(MALE if g == 'M' else FEMALE), gen3[0].first_name, g,
                       2008 + 3 * k, father=gen3[0])

        # Privacy and moderation edge cases, so each behaviour can be checked by hand.
        consent, private, unverified, trashed = gen3_all[0], gen3_all[4], gen3_all[7], gen3_all[10]
        consent.show_contact_publicly = True
        consent.biography = 'Demo: this person consented to showing their contact details publicly.'
        consent.save()
        private.is_private = True
        private.biography = 'Demo: private living person; must not appear on public pages.'
        private.save()
        unverified.is_verified = False
        unverified.biography = 'Demo: unverified record; must not appear on public pages.'
        unverified.save()
        trashed.soft_delete(user=su)
        self.stats.update(consent=consent, private=private, unverified=unverified, trashed=trashed)

        for p in gen3_all[:6]:
            self.make(PersonEducation, person=p, institution=self.pick(['University of Juba', 'Makerere University',
                                                                          'University of Nairobi', 'Lainya Secondary School']),
                      qualification=self.pick(['Bachelor of Science', 'Diploma in Education', 'Master of Arts']),
                      field_of_study=self.pick(['Civil Engineering', 'Public Health', 'History', 'Economics']),
                      start_year=str(int(p.birth_year) + 18), end_year=str(int(p.birth_year) + 22))
            self.make(PersonCareer, person=p, employer=self.pick(['Ministry of Health', 'Juba Teaching Hospital',
                                                                   'Central Equatoria State', 'Lainya County NGO Forum']),
                      position=p.occupation, location='Juba', start_year=str(int(p.birth_year) + 23), is_current=True,
                      description='Leads a small team and mentors young professionals from the community.')

        for n, p in enumerate(deceased[:6]):
            self.make(MemorialRecord, person=p, is_featured=n < 2, submitted_by=TAG,
                      burial_place=f'Family graveyard, {p.clan.name}',
                      epitaph=self.pick(['A tree with deep roots does not fear the wind.',
                                         'He who plants for his grandchildren is never forgotten.',
                                         'Her songs still carry across the valley.']),
                      tribute=(f'{p.full_name} is remembered as a generous host and a wise counsellor. '
                               f'Neighbours came to the homestead to settle disputes, and the children of the '
                               f'payam learned the clan songs there in the evenings.'),
                      survived_by='Children, grandchildren and great-grandchildren across South Sudan and the diaspora.')

        categories = ['leadership', 'education', 'culture', 'service', 'sport', 'business', 'religion', 'other']
        for n, cat in enumerate(categories):
            p = (gen2_all + gen3_all)[n * 2]
            self.make(Achievement, person_name=p.full_name, person=p, clan=p.clan, category=cat,
                      title={'leadership': 'Elected county commissioner',
                             'education': 'First woman from the payam to earn a PhD',
                             'culture': 'Recorded 40 traditional songs for the archive',
                             'service': 'Built a borehole serving three bomas',
                             'sport': 'Represented South Sudan at the regional athletics championship',
                             'business': 'Founded a honey cooperative with 200 members',
                             'religion': 'Ordained first pastor of the local parish',
                             'other': 'Translated the clan history into English'}[cat],
                      description='Recognised by the community for lasting work that benefits the Pojulu people.',
                      year=str(self.rnd.randint(1995, 2025)), source='Community nomination (demo)',
                      is_verified=n != 7, is_featured=n < 3)

        cultural = [
            ('song', 'Song of the first rains', 'Sung by women while planting sorghum after the first rains.'),
            ('song', 'Cattle praise song', 'Young men sing the names and colours of their bulls.'),
            ('proverb', 'The goat that wanders is eaten by the leopard', 'Warns children to stay close to the family.'),
            ('proverb', 'One finger cannot pick up a grain', 'Used at meetings to call for cooperation.'),
            ('ceremony', 'Seventh-day naming ceremony', 'The newborn is brought outside and given a name by the grandmother.'),
            ('story', 'How the tortoise got its shell', 'A story told to children around the evening fire.'),
            ('folklore', 'The spirit of the granite hill', 'A legend explaining why no one builds on the hilltop.'),
            ('dance', 'Harvest dance', 'Performed after the harvest, with drums and ankle rattles.'),
            ('language', 'Greetings through the day', 'Morning, afternoon and evening greetings and their replies.'),
            ('other', 'Making a clay water pot', 'Step-by-step description of traditional pottery.'),
        ]
        for n, (kind, title, context) in enumerate(cultural):
            self.make(CulturalRecord, title=title, record_type=kind, clan=live[n % len(live)],
                      content=f'{title}. (Demo content: replace with the recorded text.)',
                      context=context, performers='Elders and community members',
                      language='Pojulu', source=f'Recorded from a {live[n % len(live)].name} elder (demo)',
                      is_verified=n != 9, is_featured=n < 3,
                      image=picture(initials(title), n) if n % 3 == 0 else None)

        topics = ['Clan origins, migration', 'Marriage customs, bride wealth', 'The 1955 flood, rebuilding',
                  'Rain-making, ancestral shrines', 'Schools and churches, independence years']
        today = date(2026, 11, 4)
        for n, elder in enumerate(elders[:5] + [None]):
            name = elder.full_name if elder else f'{self.pick(FEMALE)} {self.pick(MALE)}'
            iv = self.make(ElderInterview, elder_name=name, elder_person=elder, clan=live[n % len(live)],
                           payam=live[n % len(live)].payam, approximate_age=self.rnd.randint(72, 94),
                           interview_date=today - timedelta(days=40 * n + 10),
                           interview_location=f'Homestead in {live[n % len(live)].name}',
                           interviewer=self.pick(['PHF field team', 'Demo Interviewer']),
                           summary=f'{name} speaks about {topics[n % 5].lower()} and the families of the clan.',
                           transcript='Q: Where were you born?\nA: Under the big tamarind tree near the river...\n(demo transcript)',
                           topics_covered=topics[n % 5], is_published=elder is not None, is_featured=n < 2,
                           photo_of_elder=picture(initials(name), n + 2))
            iv.clans_mentioned.add(*live[:2])

        now = timezone.now()
        news = [
            ('news', 'Archive passes 100 family records', False),
            ('event', 'Pojulu Cultural Day 2026', True),
            ('event', 'Elders storytelling evening in Lainya', True),
            ('announcement', 'Call for old family photographs', False),
            ('story', 'How a lost song was found again', False),
            ('update', 'New clan pages for Wujiyo and Mukayo', False),
            ('news', 'Scholarship fund opens for 2027', False),
            ('story', 'Three generations of teachers', False),
            ('event', 'Clan history workshop (past)', False),
        ]
        for n, (kind, title, upcoming) in enumerate(news):
            start = now + timedelta(days=20 + 15 * n) if upcoming else now - timedelta(days=30 * n + 5)
            self.make(NewsPost, title=title, post_type=kind, author=su, is_published=True, is_featured=n == 0,
                      published_at=now - timedelta(days=12 * n + 1),
                      excerpt=f'{title}. A short summary shown on the news cards.',
                      content=(f'{title}.\n\nThis is demo content for testing the news pages. The Pojulu Heritage '
                               f'Foundation shares updates about the archive, events and community stories here.'),
                      event_date=start if kind == 'event' else None,
                      event_end_date=start + timedelta(hours=5) if kind == 'event' else None,
                      event_location='Lainya Community Hall' if kind == 'event' else '',
                      is_upcoming=upcoming, tags='heritage, demo',
                      cover_image=picture(initials(title), n) if n % 2 == 0 else None)
        self.make(NewsPost, title='Draft: annual report (unpublished)', post_type='news', author=su,
                  excerpt='Unpublished draft.', content='Demo draft; must not appear publicly.', is_published=False)
        old = self.make(NewsPost, title='Outdated notice (in Trash)', post_type='announcement', author=su,
                        excerpt='Deleted post.', content='Demo post that sits in the Trash.', is_published=True)
        old.soft_delete(user=su)

        self.make(Announcement, title='Demo announcement: the archive is open for submissions via clan admins',
                  body='Contact your clan administrator to add family records.')

        # Family (wills) accounts for two living people, one with a sealed will.
        for n, p in enumerate([gen3_all[1], gen3_all[2]]):
            user = User.objects.create_user(username=f'demo_family{n + 1}', password=FAMILY_PASSWORD, is_staff=False)
            self.created.append(['auth.User', user.pk])
            acc = self.make(FamilyAccount, user=user, person=p, created_by=su, must_change_password=False)
            if n == 0:
                will = Will(account=acc)
                will.set_content('Demo will: my cattle go to my eldest son.', WILL_PASSPHRASE)
                will.save()
                self.created.append([will._meta.label, will.pk])
        self.stats['su'] = su
        self.seed_heritage()

    # ── histories, territory, landmarks, evidence ─────────────────────────
    def seed_heritage(self):
        import math
        from apps.genealogy.models import FamilyHistoryChapter
        from apps.genealogy.relatives import family_generations

        clans = [c for c in self.demo('clans.Clan') if c.is_verified]
        chiefs = self.demo('clans.ClanChief')
        families = self.demo('genealogy.Family')
        persons = self.demo('genealogy.Person')

        # Territory and a boundary drawn around a point in Lainya County.
        centres = [(4.42, 30.88), (4.30, 30.97), (4.47, 31.05), (4.22, 30.86), (4.36, 31.12)]
        landmark_kinds = [('hill', 'Hill', 'A granite outcrop where elders once lit signal fires.'),
                          ('river', 'Spring', 'A spring that never dries, even in the hardest dry season.'),
                          ('tree', 'Tamarind Tree', 'A great tamarind under which disputes are settled.'),
                          ('sacred', 'Rain Shrine', 'The place where the rain-maker performs the rain rites.'),
                          ('market', 'Market', 'The weekly market where neighbouring clans trade.')]
        for i, clan in enumerate(clans):
            lat0, lng0 = centres[i % len(centres)]
            ring = []
            for k in range(10):
                angle = 2 * math.pi * k / 10
                r = 0.05 + self.rnd.uniform(-0.012, 0.012)
                ring.append([round(lng0 + r * 1.3 * math.cos(angle), 6), round(lat0 + r * math.sin(angle), 6)])
            ring.append(ring[0])
            clan.boundary_geojson = json.dumps({'type': 'Polygon', 'coordinates': [ring]})
            clan.area_estimate = f'about {self.rnd.randint(60, 220)} km² (estimate)'
            clan.territory_description = (
                f'The land of the {clan.name} people runs from the {clan.border_south.lower()} in the south to the '
                f'{clan.border_north.lower()} in the north. Elders say the first families cleared it with the '
                f'permission of the neighbouring clans, and the boundary was confirmed at a meeting of chiefs in 1952 '
                f'and marked with stones that can still be seen.\n\n'
                f'During the wars of the 1960s and 1990s many families fled to Uganda and the land lay empty; since '
                f'2005 most have returned. A boundary disagreement with a neighbouring clan over grazing land near '
                f'the river was settled by the county chiefs in 2011. (Demo text.)')
            clan.territorial_notes = clan.territorial_notes or 'The boundary stones were renewed in 2012 after the return from exile.'
            clan.save()
            for n, (kind, suffix, desc) in enumerate(landmark_kinds[:3 + (i % 2)]):
                angle = self.rnd.uniform(0, 2 * math.pi)
                dist = self.rnd.uniform(0.005, 0.03)
                lm = self.make(apps.get_model('clans.ClanLandmark'), clan=clan,
                               name=f'{clan.name} {suffix}', landmark_type=kind, order=n,
                               description=desc,
                               history=(f'The {clan.name} elders tell that the {suffix.lower()} was where the founders '
                                        f'first stopped when they arrived. It is still visited at the start of the '
                                        f'planting season. (Demo text.)'),
                               location_description=f'{self.rnd.randint(1, 6)} km {self.pick(["north", "south", "east", "west"])} of the {clan.name} market',
                               latitude=round(lat0 + dist * math.sin(angle), 6),
                               longitude=round(lng0 + dist * 1.3 * math.cos(angle), 6),
                               photo=picture(initials(f'{clan.name} {suffix}'), i + n))
                if n == 0:
                    self.attach(lm, f'{lm.name} at sunset', 'Taken from the path below the hill.', seed=i + 3)
                    self.attach(lm, f'Elders at {lm.name}', 'The yearly gathering.', seed=i + 4)

        # Chiefs: full histories; the first chief of each clan is linked to a family record.
        founders = {}
        for p in persons:
            if p.family_id and not p.father_id and p.gender == 'M' and p.is_deceased:
                founders.setdefault(p.clan_id, p)
        for n, chief in enumerate(chiefs):
            first = chief.order == 0
            chief.other_names = self.pick(['Lo-Kudu (the drummer)', 'Mata (the patient one)', 'Lo-Pita (the peacemaker)'])
            chief.birth_year = str(int(chief.start_year or 1950) - self.rnd.randint(25, 40))
            if chief.end_year:
                chief.death_year = chief.end_year
                chief.burial_place = f'Chiefs\' burial ground, {chief.clan.name}'
            chief.summary = (f'{chief.title} {chief.name} led the {chief.clan.name} clan '
                             f'{"through the hard years after the great flood" if first else "through the return from exile"}.')
            chief.how_appointed = (
                'Chosen by the council of elders after the death of the previous chief, as the eldest son of the '
                'ruling lineage, and confirmed by the district commissioner. (Demo text.)' if first else
                'Elected by the heads of families at a gathering under the tamarind tree, then confirmed by the county. (Demo text.)')
            chief.biography = (
                f'{chief.name} was born in {chief.birth_year} in a homestead near the river. As a young man he herded '
                f'his father\'s cattle and learned the clan songs from his grandmother. He married three times and had '
                f'many children, several of whom became teachers and pastors.\n\n'
                f'People remember him as a quiet man who listened for a long time before speaking. (Demo text.)')
            chief.accomplishments = (
                '- Settled the long dispute between two families over the river grazing land.\n'
                '- Gave land for the first primary school and walked to Juba to ask for teachers.\n'
                '- Organised the building of the road to the market with community labour.\n'
                '- Kept records of every marriage and bride-wealth payment in the clan. (Demo text.)')
            chief.major_events = ('The great flood of 1955; the first independence celebrations; '
                                  'a cattle-raiding crisis that he ended by negotiation. (Demo text.)')
            chief.challenges = 'He was criticised for being too close to the government administration. (Demo text.)'
            chief.legacy = ('The clan still uses the boundary stones he set, and a school is named after him. (Demo text.)')
            chief.sources = 'Interviews with elders of the clan (demo).'
            founder = founders.get(chief.clan_id)
            if first and founder:
                chief.person = founder
                chief.name = founder.full_name
            chief.save()
            if first:
                self.attach(chief, f'Portrait of {chief.name}', 'Photographed at a gathering of chiefs.', seed=n)
                self.attach(chief, 'Letter of appointment', 'From the district office.', kind='document',
                            seed=n + 2, text='DOC')

        # Families: a written history and chapters, built from the family's own records.
        for i, fam in enumerate(families):
            gens = family_generations(fam)
            if not gens:
                continue
            founder = gens[0]['entries'][0]['person']
            founder_wife = next((e['person'] for e in gens[0]['entries'][1:]), None)
            kids = gens[0]['entries'][0]['children']
            fam.written_history = (
                f'The {fam.name} traces its roots to {founder.full_name}, born around {founder.birth_year} at '
                f'{fam.origin_village or fam.clan.name}. '
                f'{("He married " + founder_wife.full_name + ", and together they") if founder_wife else "He"} '
                f'raised {len(kids)} children whose names are still recited at family gatherings: '
                f'{", ".join(k.first_name for k in kids)}.\n\n'
                f'Besides the people recorded in this archive, the family remembers many more: brothers and sisters '
                f'who died young, half-brothers from the founder\'s second marriage who settled in Yei, and cousins '
                f'now living in Kampala, Nairobi and Australia. Their names are written in the chapters below.\n\n'
                f'Today the family has {sum(len(g["entries"]) for g in gens)} recorded members across '
                f'{len(gens)} generations. (Demo text.)')
            fam.save()
            chapters = [
                ('Origins', f'{founder.birth_year}s',
                 f'{founder.first_name} came from a family of hunters. When he was a young man his father gave him '
                 f'cattle to start his own homestead near {fam.origin_village or "the river"}. (Demo text.)'),
                (f'The children of {founder.first_name}', '1940s-1970s',
                 '\n'.join(f'{k.full_name} (born {k.birth_year}): {k.occupation or "farmer"}, lived in '
                            f'{k.current_residence or "the village"}.' for k in kids)
                 + '\nTwo more children died in infancy and are remembered by name: Lemi and Kiden. (Demo text.)'),
                ('Exile and return', '1990-2005',
                 'During the war most of the family walked to the refugee settlements in northern Uganda. The '
                 'grandchildren were born there and went to school in Adjumani. After the peace agreement the elders '
                 'returned first and rebuilt the homestead. (Demo text.)'),
            ]
            for n, (title, period, body) in enumerate(chapters):
                self.make(FamilyHistoryChapter, family=fam, title=title, period=period, body=body, order=n)
            self.attach(fam, f'{fam.name} gathering', 'The whole family at Christmas.', seed=i)
            if i == 0:
                self.attach(fam, 'Land allocation certificate (staff only)', 'Kept private: shows plot numbers.',
                            is_public=False, kind='document', seed=i + 1, text='DOC')

        # Free-text relatives accounts for a few people, and evidence on other records.
        for n, p in enumerate([x for x in persons if x.occupation and not x.is_deceased and x.is_verified][:6]):
            p.relatives_notes = (
                f'Besides the relatives recorded here, {p.first_name} has four half-brothers and three half-sisters '
                f'from {({"M": "his", "F": "her"}).get(p.gender, "their")} '
                f'father\'s second marriage, living in Yei and Morobo; a grandmother on the mother\'s side, '
                f'{self.pick(FEMALE)} {self.pick(MALE)}, who died in 1979; and more than twenty cousins in Juba, '
                f'Kampala and Nairobi. (Demo text.)')
            p.save()
        for n, rec in enumerate(self.demo('memorial.MemorialRecord')[:3]):
            self.attach(rec, 'Funeral gathering', 'Family and neighbours at the burial.', seed=n)
        for n, rec in enumerate(self.demo('achievements.Achievement')[:3]):
            self.attach(rec, 'Certificate', 'Scan of the award certificate.', kind='document', seed=n, text='CERT')
        for n, rec in enumerate(self.demo('marriages.Marriage')[:2]):
            self.attach(rec, 'Wedding photo', 'Taken outside the church.', seed=n + 1)
        for n, rec in enumerate(self.demo('elders.ElderInterview')[:2]):
            self.attach(rec, 'Interview in progress', 'The field team recording at the homestead.', seed=n + 2)
        for n, rec in enumerate(self.demo('clans.ClanEvent')[:2]):
            self.attach(rec, 'Photo of the event', '', seed=n + 3)

    # ── removal ───────────────────────────────────────────────────────────
    def delete(self):
        if not manifest_path().exists():
            raise CommandError('No demo data found (manifest missing). Nothing to delete.')
        entries = json.loads(manifest_path().read_text())
        removed, files = 0, 0
        with transaction.atomic():
            for label, pk in reversed(entries):
                model = apps.get_model(label)
                manager = getattr(model, 'all_objects', model._default_manager)
                obj = manager.filter(pk=pk).first()
                if obj is None:
                    continue
                for f in obj._meta.fields:
                    value = getattr(obj, f.attname, None) if isinstance(f, models.FileField) else None
                    if value:
                        value.delete(save=False)
                        files += 1
                obj.delete()
                removed += 1
                try:
                    hist = apps.get_model(model._meta.app_label, f'Historical{model.__name__}')
                    hist.objects.filter(id=pk).delete()
                except LookupError:
                    pass
        manifest_path().unlink()
        self.stdout.write(self.style.SUCCESS(f'Removed {removed} demo records and {files} files.'))

    def report(self):
        counts = {}
        for label, _ in self.created:
            counts[label] = counts.get(label, 0) + 1
        self.stdout.write(self.style.SUCCESS('Demo data created:'))
        for label, n in sorted(counts.items()):
            self.stdout.write(f'  {label}: {n}')
        s = self.stats
        self.stdout.write(f'\nStaff logins (password {STAFF_PASSWORD}): '
                          + ', '.join(f'demo_{r.replace("_admin", "")}' for r in ROLES)
                          + ', demo_deactivated (blocked)')
        self.stdout.write(f'Family logins (password {FAMILY_PASSWORD}): demo_family1 (sealed will, passphrase '
                          f'"{WILL_PASSPHRASE}"), demo_family2')
        self.stdout.write(f'Contact shown publicly: {s["consent"].get_absolute_url()}')
        self.stdout.write(f'Private person (should 404): {s["private"].slug}')
        self.stdout.write(f'Unverified person (should 404): {s["unverified"].slug}')
        self.stdout.write(f'In Trash: {s["trashed"].full_name} and "Outdated notice (in Trash)"')
