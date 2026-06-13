from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils.text import slugify
from django.utils import timezone


POST_TYPE_CHOICES = [
    ('news',         'News'),
    ('event',        'Event'),
    ('announcement', 'Announcement'),
    ('story',        'Community Story'),
    ('update',       'Archive Update'),
]

TYPE_COLORS = {
    'news':         '1B5E20',
    'event':        '0D47A1',
    'announcement': 'B71C1C',
    'story':        '4A148C',
    'update':       '1B5E20',
}


class NewsPost(models.Model):
    title          = models.CharField(max_length=400)
    slug           = models.SlugField(max_length=440, unique=True, blank=True)
    post_type      = models.CharField(max_length=20, choices=POST_TYPE_CHOICES, default='news')
    excerpt        = models.TextField(max_length=600, help_text='Brief summary shown on news cards (2–3 sentences)')
    content        = models.TextField(help_text='Full article or event description')
    cover_image    = models.ImageField(upload_to='news/covers/', blank=True, null=True)
    video_url      = models.URLField(blank=True, help_text='YouTube or Vimeo URL — shown as video card')

    # Event-specific fields
    event_date     = models.DateTimeField(null=True, blank=True, help_text='For events: start date and time')
    event_end_date = models.DateTimeField(null=True, blank=True, help_text='For events: end date')
    event_location = models.CharField(max_length=400, blank=True)
    is_upcoming    = models.BooleanField(default=False, help_text='Mark as upcoming event')

    # Publishing
    is_published   = models.BooleanField(default=False)
    is_featured    = models.BooleanField(default=False, help_text='Pin as featured story on homepage')
    published_at   = models.DateTimeField(null=True, blank=True)
    author         = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='news_posts')

    # Meta
    views          = models.PositiveIntegerField(default=0)
    tags           = models.CharField(max_length=400, blank=True, help_text='Comma-separated tags')
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-published_at', '-created_at']
        verbose_name = 'News Post'
        verbose_name_plural = 'News & Events'

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title)
            slug, n = base, 1
            while NewsPost.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f'{base}-{n}'; n += 1
            self.slug = slug
        if self.is_published and not self.published_at:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'[{self.get_post_type_display()}] {self.title}'

    def get_absolute_url(self):
        return reverse('news:detail', kwargs={'slug': self.slug})

    @property
    def tag_list(self):
        return [t.strip() for t in self.tags.split(',') if t.strip()]

    @property
    def type_color(self):
        return TYPE_COLORS.get(self.post_type, '1B5E20')

    @property
    def has_video(self):
        return bool(self.video_url)


class NewsMedia(models.Model):
    MEDIA_TYPES = [('photo','Photo'),('document','Document'),('video','Video')]
    post       = models.ForeignKey(NewsPost, on_delete=models.CASCADE, related_name='media')
    media_type = models.CharField(max_length=20, choices=MEDIA_TYPES, default='photo')
    title      = models.CharField(max_length=300, blank=True)
    file       = models.FileField(upload_to='news/media/')
    caption    = models.TextField(blank=True)
    order      = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f'{self.get_media_type_display()}: {self.title or self.post.title}'