"""Normalize API rich text to a small, reconstruct-only HTML vocabulary."""
from html import escape
from html.parser import HTMLParser
from urllib.parse import urlsplit, urlunsplit
from rest_framework import serializers


class InlineHTML(HTMLParser):
    tags = {"b", "strong", "i", "em", "u"}

    def __init__(self, host):
        super().__init__(convert_charrefs=True)
        self.host = host
        self.output = []

    def handle_data(self, data):
        self.output.append(escape(data))

    def handle_starttag(self, tag, attrs):
        if tag in self.tags or tag == "br":
            self.output.append(f"<{tag}>")
        elif tag in {"img", "audio"}:
            raw = dict(attrs).get("src") or ""
            try:
                url = urlsplit(raw)
                if url.scheme not in ("", "http", "https") or url.username or url.password:
                    return
                if url.netloc and url.netloc != self.host:
                    return
                if not url.path.startswith(("/media/", "/static/")):
                    return
                source = escape(urlunsplit(("", "", url.path, url.query, "")), quote=True)
            except ValueError:
                return
            if tag == "img":
                self.output.append(f'<img src="{source}" alt="" loading="lazy">')
            else:
                self.output.append(f'<audio controls preload="none" src="{source}"></audio>')

    def handle_endtag(self, tag):
        if tag in self.tags:
            self.output.append(f"</{tag}>")


class RichTextField(serializers.CharField):
    def __init__(self, **kwargs):
        super().__init__(max_length=100000, **kwargs)

    def to_internal_value(self, data):
        raw = super().to_internal_value(data)
        # Bound input before parsing; CharField's validators run afterwards.
        if len(raw) > self.max_length:
            self.fail("max_length", max_length=self.max_length)
        request = self.context.get("request")
        parser = InlineHTML(request.get_host() if request else "")
        parser.feed(raw)
        parser.close()
        normalized = "".join(parser.output).strip()
        if not normalized and not self.allow_blank:
            self.fail("blank")
        return normalized
