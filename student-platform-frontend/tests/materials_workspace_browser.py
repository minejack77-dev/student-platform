"""Material editing scenarios against the disposable workstation database."""
from playwright.sync_api import expect
from pathlib import Path
from io import BytesIO


def check_materials(page, base, subject_id, topic_id, checks, artifacts):
    subject_url = f'{base}/subject/{subject_id}'
    topic_url = f'{base}/topic/{topic_id}'

    def capture(key, width):
        sizes = page.evaluate('''() => ({page:document.documentElement.scrollWidth,
          overflow:[...document.querySelectorAll('.panel-card,.question-editor,.topic-card,.task-workspace-toolbar')]
          .filter(e=>e.getClientRects().length && e.scrollWidth>e.clientWidth+2).map(e=>e.className)})''')
        assert sizes['page'] <= width + 1 and not sizes['overflow'], (key, width, sizes)
        checks.append(f'materials:{key}:{width}')
        if width in [390, 1440]:
            page.screenshot(path=str(artifacts / f'materials-{key}-{width}.png'), full_page=True, animations='disabled')

    for width in [320, 390, 768, 1440]:
        page.set_viewport_size({'width': width, 'height': 1000})
        page.goto(subject_url)
        expect(page.locator('.topic-card')).to_have_count(1)
        page.locator('.create-topic-box summary').click()
        capture('subject', width)
        page.goto(topic_url)
        expect(page.locator('.question-text')).to_have_count(1)
        page.get_by_role('button', name='Новый вопрос', exact=True).click()
        expect(page.locator('.question-editor')).to_be_visible()
        if width < 640:
            assert page.locator('.choice-field textarea').first.bounding_box()['width'] > 160
        capture('editor', width)
        for label, key in [('Настройки теста', 'settings'), ('Импорт', 'import')]:
            page.locator('.workspace-tabs').get_by_role('button', name=label, exact=True).click()
            capture(key, width)

    page.goto(subject_url)
    search = page.get_by_label('Найти тему или учебник')
    search.fill('нетсовпадений')
    expect(page.locator('.topic-card')).to_have_count(0)
    page.get_by_role('button', name='Очистить поиск').click()
    expect(page.locator('.topic-card')).to_have_count(1)
    page.locator('.create-topic-box summary').click()
    page.locator('.create-topic-box button').click()
    expect(page.locator('#create-topic-error[role="alert"]')).to_be_visible()
    page.locator('#topic-title').fill('Тема браузерной проверки')
    page.locator('.page-breadcrumbs a').first.click()
    expect(page.get_by_role('dialog')).to_be_visible()
    page.keyboard.press('Escape')
    expect(page.locator('#topic-title')).to_have_value('Тема браузерной проверки')
    page.locator('#topic-new_workbook_title').fill('Учебник проверки')
    page.locator('#topic-new_unit_title').fill('Раздел проверки')
    with page.expect_response(lambda r: '/api/topic/' in r.url and r.request.method == 'POST') as response:
        page.locator('.create-topic-box button').click()
    assert response.value.status == 201, response.value.text()
    new_topic = response.value.json()['id']
    expect(page.locator('.topic-card')).to_have_count(2)
    checks.append('materials:search-validation-create-topic')

    page.goto(f'{base}/topic/{new_topic}')
    page.locator('.workspace-actions').get_by_role('button', name='Создать тест').click()
    page.locator('#topic-field-4').fill('Тест браузерной проверки')
    page.locator('#topic-field-6').fill('1')
    page.locator('#topic-field-7').fill('1')
    with page.expect_response(lambda r: '/api/task/' in r.url and r.request.method == 'POST') as response:
        page.locator('.new-task-btn').click()
    assert response.value.status == 201, response.value.text()
    page.locator('.workspace-tabs').get_by_role('button', name='Вопросы', exact=True).click()
    page.get_by_role('button', name='Новый вопрос', exact=True).click()
    page.get_by_label('Вопрос', exact=True).fill('Сохранённый <strong>вопрос</strong>')
    page.get_by_label('Вариант 1', exact=True).fill('Правильный')
    page.get_by_label('Вариант 2', exact=True).fill('Неверный')
    page.locator('.correct-choice-label input').first.check()
    page.reload()
    expect(page.get_by_label('Вопрос', exact=True)).to_have_value('Сохранённый <strong>вопрос</strong>')
    from PIL import Image
    image = BytesIO()
    Image.new('RGB', (40, 30), color='navy').save(image, format='PNG')
    page.locator('.question-image-input').set_input_files({'name':'fixture.png', 'mimeType':'image/png', 'buffer':image.getvalue()})
    expect(page.locator('.question-editor img')).to_have_count(1)
    page.get_by_role('button', name='Новый вопрос', exact=True).click()
    expect(page.get_by_role('dialog')).to_be_visible()
    page.keyboard.press('Escape')
    expect(page.locator('.question-editor img')).to_have_count(1)
    page.locator('.page-breadcrumbs a').first.click()
    expect(page.get_by_role('dialog')).to_be_visible()
    page.keyboard.press('Escape')
    expect(page.locator('.question-editor img')).to_have_count(1)
    held = []
    page.route('**/api/question/', lambda route: held.append(route) if route.request.method == 'POST' else route.continue_())
    with page.expect_response(lambda r: '/api/question/' in r.url and r.request.method == 'POST') as response:
        page.get_by_role('button', name='Создать вопрос', exact=True).click()
        expect(page.get_by_role('button', name='Новый вопрос', exact=True)).to_be_disabled()
        expect(page.locator('.task-workspace-toolbar select')).to_be_disabled()
        expect(page.get_by_label('Вопрос', exact=True)).to_be_disabled()
        page.locator('.workspace-tabs').get_by_role('button', name='Настройки теста', exact=True).click()
        details = page.locator('details.new-task-section')
        if details.count() and not details.get_attribute('open'):
            details.locator('summary').click()
        expect(page.locator('.new-task-btn')).to_be_disabled()
        expect(page.locator('.task-settings-btn')).to_be_disabled()
        page.locator('.workspace-tabs').get_by_role('button', name='Вопросы', exact=True).click()
        assert len(held) == 1
        held[0].continue_()
    page.unroute('**/api/question/')
    assert response.value.status == 201, response.value.text()
    expect(page.locator('.question-text strong')).to_have_text('вопрос')
    expect(page.locator('.question-item img')).to_have_count(1)
    page.locator('.ghost-edit-btn').click()
    page.get_by_label('Вопрос', exact=True).fill('Черновик для смены редактора')
    page.get_by_role('button', name='Новый вопрос', exact=True).click()
    page.locator('dialog .btn-primary').click()
    expect(page.get_by_label('Вопрос', exact=True)).to_have_value('')
    page.locator('.ghost-edit-btn').click()
    page.get_by_label('Вопрос', exact=True).fill('Обновлённый вопрос')
    page.locator('.editor-actions .btn-primary').click()
    expect(page.locator('.question-text')).to_have_text('Обновлённый вопрос')
    page.locator('.question-actions .ghost-danger-btn').click()
    expect(page.get_by_role('dialog')).to_be_visible()
    page.keyboard.press('Escape')
    expect(page.locator('.question-actions .ghost-danger-btn')).to_be_focused()
    page.locator('.question-actions .ghost-danger-btn').click()
    page.locator('dialog .btn-primary').click()
    expect(page.locator('.question-text')).to_have_count(0)
    checks.append('materials:create-task-question-draft-richtext-edit-delete')
    checks.append('materials:editor-replacement-guard-and-pending-save-lock')

    page.locator('.workspace-tabs').get_by_role('button', name='Импорт', exact=True).click()
    template = Path(__file__).resolve().parents[1] / 'public/templates/single_choice.xlsx'
    page.locator('#question-import-file').set_input_files(str(template))
    page.locator('.import-btn').click()
    expect(page.locator('.alert-info .btn-primary')).to_be_visible()
    page.locator('.alert-info .btn-primary').click()
    expect(page.get_by_role('button', name='Отменить последний импорт', exact=True)).to_be_visible()
    page.locator('.workspace-tabs').get_by_role('button', name='Вопросы', exact=True).click()
    expect(page.locator('.question-text').first).to_be_visible()
    page.locator('.workspace-tabs').get_by_role('button', name='Импорт', exact=True).click()
    page.get_by_role('button', name='Отменить последний импорт', exact=True).click()
    page.locator('dialog .btn-primary').click()
    expect(page.get_by_role('dialog')).to_have_count(0)
    page.locator('.workspace-tabs').get_by_role('button', name='Вопросы', exact=True).click()
    expect(page.locator('.question-text')).to_have_count(0)
    checks.append('materials:image-upload-import-preview-commit-undo')

    page.route('**/api/question/**', lambda route: route.fulfill(status=503, json={'detail':'Temporary questions error'}))
    page.goto(topic_url)
    expect(page.locator('.alert-danger[role="alert"]')).to_contain_text('Не удалось загрузить вопросы')
    expect(page.locator('.empty-box:visible')).to_have_count(0)
    page.unroute('**/api/question/**')
    page.get_by_role('button', name='Повторить', exact=True).click()
    expect(page.locator('.question-text')).to_have_count(1)
    checks.append('materials:questions-error-retry')
