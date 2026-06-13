from apps.clans.models import Clan


def site_context(request):
    return {
        'site_name': 'Pojulu Heritage Foundation',
        'site_tagline': 'Preserving Our Roots, Empowering Our Future',
        'all_clans': Clan.objects.filter(is_verified=True).values('name', 'slug')[:30],
        'nav_locations': [
            ('Lainya Centre', 'lainya_centre'),
            ('Kupera', 'kupera'),
            ('Kenyi', 'kenyi'),
            ('Wuji', 'wuji'),
            ('Mukaya', 'mukaya'),
            ('Wonduruba', 'wonduruba'),
            ('Yei County', 'yei_county'),
        ],
    }
