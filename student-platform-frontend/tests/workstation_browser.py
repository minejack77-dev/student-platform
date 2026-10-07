"""Workspace navigation regression against a real build and disposable Django DB.

Run after npm run build. Requires Django, Python Playwright and local Chrome.
An optional local dependency directory is .runlogs/browser-test-deps.
All created users, groups, assignments and attempts live in a temporary database.
"""
from datetime import timedelta
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import threading
from wsgiref.simple_server import make_server, WSGIRequestHandler

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / '.runlogs/browser-test-deps'))
sys.path.extend([str(ROOT.parent / 'audit/backend'), str(ROOT.parent / 'audit/tools')])
ARTIFACTS = ROOT / '.runlogs/workstation-review'


class QuietHandler(WSGIRequestHandler):
    def log_message(self, *args):
        pass


def run():
    ARTIFACTS.mkdir(exist_ok=True)
    with TemporaryDirectory(prefix='workstation-browser-') as temporary:
        os.environ.update(DJANGO_SETTINGS_MODULE='config.settings', DJANGO_ENV='test',
                          DJANGO_DB_NAME=str(Path(temporary) / 'test.sqlite3'),
                          DJANGO_MEDIA_ROOT=str(Path(temporary) / 'media'),
                          DJANGO_ALLOWED_HOSTS='127.0.0.1,localhost')
        import django
        django.setup()
        from django.core.management import call_command
        from django.core.wsgi import get_wsgi_application
        from django.contrib.staticfiles.handlers import StaticFilesHandler
        from django.db import connections
        from django.utils import timezone
        from accounts.models import User, Teacher, Student
        from learning.models import Subject, Topic, Task, Question, Choice, Group, GroupStudent, GroupTeachingAssignment, GroupTopicSchedule, Attempt, AttemptQuestion, Answer
        from playwright.sync_api import sync_playwright, expect

        call_command('migrate', verbosity=0, interactive=False)
        password = 'Synthetic-Workspace-Test42!'
        teacher_user = User.objects.create_superuser(username='teacher_fixture', password=password, role='teacher')
        teacher = Teacher.objects.create(user=teacher_user)
        student_user = User.objects.create_user(username='student_fixture', password=password, role='student')
        student, _ = Student.objects.get_or_create(user=student_user)
        extra_user = User.objects.create_user(username='new_member_fixture', password=password, role='student')
        Student.objects.get_or_create(user=extra_user)
        subject = Subject.objects.create(name='Английский язык', description='Грамматика и практика', owner=teacher_user)
        Subject.objects.create(name='Математика', description='Задачи и контрольные работы', owner=teacher_user)
        topic = Topic.objects.create(subject=subject, title='Времена английского языка')
        tasks = []
        for title in ['Present Perfect — практика', 'Повторение пройденного материала', 'Следующее занятие']:
            task = Task.objects.create(topic=topic, title=title, questions_per_attempt=1, passing_correct_answers=1)
            question = Question.objects.create(topic=topic, task=task, text='Choose the correct answer', question_type='single_choice')
            Choice.objects.create(question=question, text='Correct', is_correct=True)
            Choice.objects.create(question=question, text='Incorrect', is_correct=False)
            tasks.append(task)
        groups = []
        for name, description in [('11А', 'Подготовка к выпускным экзаменам'), ('11Б', 'Основная учебная группа'), ('Группа_' + 'длинноеназвание' * 5, 'Проверка переноса длинных названий')]:
            group = Group.objects.create(name=name, description=description, teacher=teacher)
            GroupTeachingAssignment.objects.create(group=group, teacher=teacher, subject=subject, topic=topic, task=tasks[0])
            groups.append(group)
        GroupStudent.objects.create(group=groups[0], student=student)
        for index, task in enumerate(tasks):
            GroupTopicSchedule.objects.create(group=groups[0], teacher=teacher, topic=topic, task=task,
                                              scheduled_for=timezone.localdate() + timedelta(days=1 if index == 2 else 0))
        previous = GroupTopicSchedule.objects.create(group=groups[0], teacher=teacher, topic=topic, task=tasks[0],
                                                     scheduled_for=timezone.localdate() - timedelta(days=1))
        completed = Attempt.objects.create(student=student, topic=topic, task=tasks[0], schedule_entry=previous)
        question = tasks[0].questions.first()
        attempt_question = AttemptQuestion.objects.create(attempt=completed, question=question, order=1)
        answer = Answer.objects.create(attempt_question=attempt_question)
        answer.selected_choices.add(question.choices.get(is_correct=True))
        completed.status = 'completed'
        completed.finished_at = timezone.now()
        completed.save()
        application = StaticFilesHandler(get_wsgi_application())
        server = make_server('127.0.0.1', 0, application, handler_class=QuietHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f'http://127.0.0.1:{server.server_port}'
        checks = []
        errors = []

        def login(browser, username):
            context = browser.new_context(service_workers='block', locale='ru-RU', viewport={'width': 1440, 'height': 1000})
            context.request.get(base + '/api/auth/csrf/')
            csrf = next(c['value'] for c in context.cookies() if c['name'] == 'csrftoken')
            response = context.request.post(base + '/api/auth/login/', data={'username': username, 'password': password}, headers={'X-CSRFToken': csrf})
            assert response.status == 200, response.text()
            page = context.new_page()
            page.on('pageerror', lambda error: errors.append(str(error)))
            return context, page

        def nav(page, label):
            page.get_by_role('navigation', name='Основная навигация').get_by_role('link', name=label, exact=True).click()
            expect(page.get_by_role('heading', level=1)).to_have_text(label)
            expect(page.locator('.sidebar-link[aria-current="page"]')).to_have_count(1)

        def matrix(page, role, views):
            for width in [320, 390, 768, 1440]:
                page.set_viewport_size({'width': width, 'height': 1000})
                for label in views:
                    nav(page, label)
                    # No overflow masking: test document and visible content containers.
                    sizes = page.evaluate('''() => ({viewport: innerWidth, page: document.documentElement.scrollWidth,
                        overflowing: [...document.querySelectorAll('.section-card, .entity-card, .schedule-day-card')]
                        .filter(e => e.getClientRects().length && e.scrollWidth > e.clientWidth + 2).map(e => e.className)})''')
                    assert sizes['page'] <= width + 1 and not sizes['overflowing'], (role, label, width, sizes)
                    checks.append(f'{role}:{label}:{width}')
                    if width in [390, 1440] and label == views[0]:
                        page.screenshot(path=str(ARTIFACTS / f'{role}-{width}.png'), full_page=True)

        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(channel='chrome', headless=True)
                teacher_context, page = login(browser, teacher_user.username)
                page.goto(base + '/')
                expect(page.get_by_role('heading', level=1)).to_have_text('Группы')
                expect(page.locator('.entity-title:visible')).to_have_count(3)
                page.get_by_role('button', name='Добавить группу').click()
                page.get_by_role('button', name='Создать', exact=True).click()
                expect(page.locator('#create-group-error[role="alert"]')).to_be_visible()
                expect(page.get_by_label('Название группы', exact=True)).to_have_attribute('aria-invalid', 'true')
                page.get_by_label('Название группы', exact=True).fill('Черновик новой группы')
                nav(page, 'Материалы')
                page.go_back()
                expect(page.get_by_label('Название группы', exact=True)).to_have_value('Черновик новой группы')
                page.go_forward()
                expect(page.get_by_role('heading', level=1)).to_have_text('Материалы')
                nav(page, 'Группы')
                page.get_by_role('button', name='Отмена', exact=True).click()
                search = page.get_by_role('textbox', name='Найти группу')
                search.fill('11А')
                expect(page.locator('.entity-title:visible')).to_have_count(1)
                search.fill('нетсовпадений')
                expect(page.locator('.empty-box:visible')).to_be_visible()
                search.fill('')
                expect(page.locator('.entity-title:visible')).to_have_count(3)
                nav(page, 'Результаты')
                expect(page.locator('.entity-link-primary:visible').first).to_have_attribute('href', f'/group/{groups[0].pk}/overview?tab=results')
                page.reload()
                expect(page.get_by_role('heading', level=1)).to_have_text('Результаты')
                page.goto(base + '/?view=unknown')
                expect(page.get_by_role('heading', level=1)).to_have_text('Группы')
                matrix(page, 'teacher', ['Группы', 'Материалы', 'Результаты'])
                page.locator('#app-language-select').select_option('en')
                expect(page.get_by_role('heading', level=1)).to_have_text('Results')
                expect(page.locator('html')).to_have_attribute('lang', 'en')
                page.locator('#app-language-select').select_option('ru')
                # Retry after an actual failed HTTP response.
                page.route('**/api/group/**', lambda route: route.fulfill(status=503, json={'detail': 'Synthetic temporary error'}))
                page.goto(base + '/')
                expect(page.get_by_role('alert')).to_be_visible()
                page.unroute('**/api/group/**')
                page.get_by_role('button', name='Повторить', exact=False).click()
                expect(page.locator('.entity-title:visible')).to_have_count(3)
                checks += ['teacher:draft-back-forward', 'teacher:search-empty', 'teacher:results-link-refresh', 'teacher:unknown-view', 'teacher:ru-en', 'teacher:error-retry']
                from group_workspace_browser import check_group_workspace
                check_group_workspace(page, base, groups[0].pk, groups[1].pk, tasks[0].pk, previous.scheduled_for.isoformat(), checks, ARTIFACTS)
                from materials_workspace_browser import check_materials
                check_materials(page, base, subject.pk, topic.pk, checks, ARTIFACTS)
                teacher_context.close()

                student_context, page = login(browser, student_user.username)
                page.goto(base + '/student')
                expect(page.get_by_role('heading', level=1)).to_have_text('Мои тесты')
                expect(page.locator('.today-task-item')).to_have_count(2)
                matrix(page, 'student', ['Мои тесты', 'Расписание', 'Результаты', 'Уведомления'])
                nav(page, 'Результаты')
                expect(page.locator('.recent-result-item')).to_have_count(1)
                history_search = page.locator('.recent-results-head').locator('..').get_by_role('textbox')
                history_search.fill('нетсовпадений')
                expect(page.locator('.recent-result-item')).to_have_count(0)
                page.locator('.empty-box:visible .btn-link').click()
                expect(history_search).to_have_value('')
                expect(page.locator('.recent-result-item')).to_have_count(1)
                nav(page, 'Расписание')
                page.reload()
                expect(page.get_by_role('heading', level=1)).to_have_text('Расписание')
                nav(page, 'Мои тесты')
                page.locator('.today-task-item button').first.click()
                expect(page.get_by_role('dialog')).to_be_visible()
                page.keyboard.press('Escape')
                expect(page.get_by_role('dialog')).to_have_count(0)
                expect(page.locator('.today-task-item button').first).to_be_focused()
                page.route('**/api/attempt/**', lambda route: route.fulfill(status=503, json={'detail': 'Synthetic temporary error'}))
                page.locator('.today-task-item button').first.click()
                page.locator('dialog .btn-primary').click()
                expect(page.get_by_role('alert')).to_be_visible()
                page.unroute('**/api/attempt/**')
                page.locator('.today-task-item button').first.click()
                page.locator('dialog .btn-primary').click()
                page.wait_for_url('**/attempt/*')
                expect(page.locator('.attempt-page')).to_be_visible()
                page.get_by_role('navigation', name='Основная навигация').get_by_role('link', name='Мои тесты', exact=True).click()
                expect(page.get_by_role('button', name='Продолжить', exact=True)).to_be_visible()
                page.get_by_role('button', name='Выйти', exact=True).click()
                page.wait_for_url('**/login')
                expect(page.locator('.workspace-sidebar')).to_have_count(0)
                checks += ['teacher:form-error-announcement', 'student:history-search-clear', 'student:start-error-announcement', 'student:refresh', 'student:start-cancel-focus', 'student:start-real-attempt', 'student:continue', 'logout:guest-shell']
                student_context.close()
                browser.close()
            assert not errors, errors
            report = {'status': 'passed', 'checks': checks, 'javascript_errors': errors, 'database': 'temporary', 'screenshots': str(ARTIFACTS)}
            (ARTIFACTS / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            print(json.dumps({'status': 'passed', 'checks': len(checks), 'javascript_errors': len(errors)}))
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()
            connections.close_all()


if __name__ == '__main__':
    run()
