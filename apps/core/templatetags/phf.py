from django import template

from apps.core.embeds import embed_url as _embed_url

register = template.Library()


@register.filter
def embed_url(url):
    """Safe iframe src for a YouTube/Vimeo link, or '' if not one."""
    return _embed_url(url)


@register.simple_tag(takes_context=True)
def absolute_uri(context, url):
    """Absolute URL for meta tags (OpenGraph needs scheme + host)."""
    if not url:
        return ''
    if url.startswith(('http://', 'https://')):
        return url
    request = context.get('request')
    return request.build_absolute_uri(url) if request else url


@register.simple_tag(takes_context=True)
def page_url(context, page, param='page'):
    """Current query string with the page parameter replaced — keeps every
    active filter (and the other table's page on two-table dashboards)."""
    params = context['request'].GET.copy()
    params[param or 'page'] = page
    return '?' + params.urlencode()
