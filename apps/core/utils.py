MAX_QUERY_LENGTH = 100
MIN_QUERY_LENGTH = 2


def search_term(request, param='q'):
    """The trimmed, length-capped search string from the query string."""
    return request.GET.get(param, '').strip()[:MAX_QUERY_LENGTH]
