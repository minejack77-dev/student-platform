"""Headless Chrome regressions on a disposable Django DB and real Vue build.

Requires Python Playwright + Django dependencies and a local Chrome install.
The audit tools directory is an optional dependency source for this workspace.
"""
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import threading
from wsgiref.simple_server import make_server, WSGIRequestHandler

ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT.parent / "audit"
sys.path.insert(0, str(ROOT))
sys.path.extend([str(AUDIT / "backend"), str(AUDIT / "tools")])


class QuietHandler(WSGIRequestHandler):
    def log_message(self, *args):
        pass


def run():
    with TemporaryDirectory(prefix="rich-text-security-") as temporary:
        os.environ.update(
            DJANGO_SETTINGS_MODULE="config.settings",
            DJANGO_ENV="test",
            DJANGO_DB_NAME=str(Path(temporary) / "test.sqlite3"),
            DJANGO_MEDIA_ROOT=str(Path(temporary) / "media"),
            DJANGO_ALLOWED_HOSTS="127.0.0.1,localhost",
        )
        import django
        django.setup()
        from django.core.management import call_command
        from django.core.wsgi import get_wsgi_application
        from django.contrib.staticfiles.handlers import StaticFilesHandler
        from django.db import connections
        from accounts.models import User, Teacher
        from learning.models import Subject, Topic, Task, Question
        from playwright.sync_api import sync_playwright

        call_command("migrate", verbosity=0, interactive=False)
        user = User.objects.create_superuser(username="browser_security", password="Synthetic-Browser-Test42!", role="teacher")
        Teacher.objects.create(user=user)
        subject = Subject.objects.create(name="Browser security")
        topic = Topic.objects.create(subject=subject, title="Security lesson")
        task = Task.objects.create(topic=topic, title="Security task")
        payload = '<img src="/security-probe" onerror="window.__security_marker=1">Stored security question'
        Question.objects.create(topic=topic, task=task, text=payload)
        application = StaticFilesHandler(get_wsgi_application())
        helper = (ROOT / "student-platform-frontend/src/utils/richText.js").read_bytes()

        def app(environ, start_response):
            if environ["PATH_INFO"] == "/test-rich-text.js":
                start_response("200 OK", [("Content-Type", "application/javascript")])
                return [helper]
            return application(environ, start_response)

        server = make_server("127.0.0.1", 0, app, handler_class=QuietHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(channel="chrome", headless=True)
                context = browser.new_context(service_workers="block")
                context.request.get(base + "/api/auth/csrf/")
                csrf = next(c["value"] for c in context.cookies() if c["name"] == "csrftoken")
                response = context.request.post(base + "/api/auth/login/", data={"username": user.username, "password": "Synthetic-Browser-Test42!"}, headers={"X-CSRFToken": csrf})
                assert response.status == 200
                csrf = next(c["value"] for c in context.cookies() if c["name"] == "csrftoken")
                response = context.request.post(base + "/api/question/", data={
                    "topic": topic.pk, "task": task.pk, "text": payload,
                    "question_type": "single_choice", "choices": [
                        {"text": "<b>Correct</b>", "is_correct": True},
                        {"text": "Wrong", "is_correct": False},
                    ],
                }, headers={"X-CSRFToken": csrf})
                assert response.status == 201, response.text()
                page = context.new_page()
                probes = []

                def record_and_block(route):
                    probes.append(route.request.url)
                    route.abort()

                page.route("**/security-probe**", record_and_block)
                page.goto(base + f"/topic/{topic.pk}?task={task.pk}")
                page.locator(".question-text").filter(has_text="Stored security question").first.wait_for()
                result = page.evaluate("""async () => {
                    const m = await import('/test-rich-text.js');
                    const payloads = [
                        '<img src="/security-probe" onerror="window.__security_marker=1">text',
                        '<svg onload="window.__security_marker=1"><image href="/security-probe"/></svg>',
                        '<audio autoplay src="/security-probe" onerror="window.__security_marker=1"></audio>',
                        '<math><mtext><table><mglyph><style><!--</style><img title="--><img src=/security-probe onerror=window.__security_marker=1>">',
                        '<img src="javascript:alert(1)"><img src="data:image/svg+xml,x">',
                        '<img src="//example.invalid/security-probe"><iframe src="/security-probe"></iframe>',
                        '<img src="/media/x&quot; onerror=&quot;window.__security_marker=1">',
                    ];
                    const results = [];
                    for (const raw of payloads) {
                        const safe = m.sanitizeInlineRichText(raw);
                        const plain = m.plainTextFromRichText(raw);
                        const lines = m.extractRichTextLines('<div>' + raw + '</div>');
                        const rendered = document.createElement('div');
                        rendered.innerHTML = safe;
                        document.body.append(rendered);
                        results.push({safe, plain, lines});
                    }
                    const formatting = m.sanitizeInlineRichText('<b>B</b><i>I</i><u>U</u><img src="/media/image.png">');
                    const lines = m.extractRichTextLines('<div><b>One</b></div><div><i>Two</i></div>');
                    await new Promise(resolve => setTimeout(resolve, 250));
                    return {results, formatting, lines, marker: window.__security_marker || null};
                }""")
                assert result["marker"] is None, result
                assert not probes, probes
                assert result["lines"] == ["<b>One</b>", "<i>Two</i>"]
                assert "<b>B</b><i>I</i><u>U</u>" in result["formatting"]
                assert "/media/image.png" in result["formatting"]
                for item in result["results"]:
                    assert "<svg" not in item["safe"] and "<iframe" not in item["safe"]
                print(json.dumps({"stored_question": "passed", "helper_payloads": len(result["results"]), "marker": None, "network_callbacks": len(probes), "formatting": "passed"}))
                browser.close()
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()
            connections.close_all()


if __name__ == "__main__":
    run()
