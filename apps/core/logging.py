"""One-line JSON log records for Railway's log viewer (searchable, no
multi-line tracebacks splitting across entries)."""
import json
import logging
from datetime import datetime, timezone

_STANDARD = set(vars(logging.makeLogRecord({}))) | {'message', 'asctime'}


class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            'ts': datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(timespec='milliseconds'),
            'level': record.levelname,
            'logger': record.name,
            'msg': record.getMessage(),
        }
        # Structured extras passed via logger.info(..., extra={...}).
        for key, value in record.__dict__.items():
            if key not in _STANDARD and not key.startswith('_') and key not in ('request', 'server_time'):
                try:
                    json.dumps(value)
                    payload[key] = value
                except TypeError:
                    payload[key] = str(value)
        if getattr(record, 'status_code', None):
            payload['status'] = record.status_code
        if record.exc_info:
            payload['exc'] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)
