"""Real API regression for the test-first materials workflow and refreshed shell."""
from datetime import timedelta
from playwright.sync_api import expect


def check_materials_flow(page, base, subject_id, group_id, checks, artifacts):
    from django.utils import timezone

    def capture(name, width):
        page.set_viewport_size({'width': width, 'height': 1000})
        page.evaluate('window.scrollTo(0, 0)')
        sizes = page.evaluate('''() => ({width: innerWidth, page: document.documentElement.scrollWidth,
          top: document.querySelector('main').getBoundingClientRect().top,
          overflow: [...document.querySelectorAll('.material-library,.flow-editor,.material-create-form')]
            .filter(e => e.getClientRects().length && e.scrollWidth > e.clientWidth + 2).map(e => e.className)})''')
        assert sizes['page'] <= width + 1 and not sizes['overflow'], (name, width, sizes)
        if width <= 800:
            assert sizes['top'] <= 140, sizes
        checks.append(f'update:{name}:{width}')
        if width in (390, 1440):
            page.screenshot(path=str(artifacts / f'update-{name}-{width}.png'), full_page=True, animations='disabled')

    page.goto(base + '/?view=materials')
    expect(page.locator('.material-test-link').first).to_be_visible()
    for width in (320, 390, 768, 1440):
        capture('library', width)
    page.locator('.account-trigger').click()
    page.locator('#app-language-select').select_option('en')
    expect(page.get_by_role('heading', level=1)).to_have_text('Materials')
    page.locator('#app-language-select').select_option('ru')
    page.keyboard.press('Escape')
    expect(page.locator('.account-trigger')).to_be_focused()
    expect(page.locator('.account-panel')).to_have_count(0)
    page.emulate_media(reduced_motion='reduce')
    page.locator('.account-trigger').click()
    duration = page.locator('.account-panel').evaluate('e => getComputedStyle(e).transitionDuration')
    assert all(float(part.strip().rstrip('s')) < 0.01 for part in duration.split(',')), duration
    page.keyboard.press('Escape')
    page.emulate_media(reduced_motion='no-preference')
    checks.append('update:account-escape-focus-ru-en-reduced-motion')

    search = page.get_by_label('Поиск по названию теста')
    await_clear = '''async () => {
      const input = document.querySelector('.material-search input');
      input.value = 'rapid'; input.dispatchEvent(new Event('input', { bubbles: true }));
      await Promise.resolve();
      document.querySelector('.clear-filters').click();
    }'''
    page.evaluate(await_clear)
    expect(page.locator('.library-loading')).to_have_count(0)
    expect(page.locator('.material-test-link').first).to_be_visible()
    checks.append('update:clear-during-debounce-same-url')
    search.fill('нетсовпадений')
    expect(page.get_by_role('heading', name='По этим условиям тестов нет')).to_be_visible()
    page.reload()
    expect(search).to_have_value('нетсовпадений')
    page.locator('.library-state').get_by_role('button', name='Сбросить фильтры').click()
    expect(page.locator('.material-test-link').first).to_be_visible()
    search.fill('Present')
    expect(page.locator('.material-test-link')).to_have_count(1)
    page.locator('.material-test-link').click()
    expect(page.locator('.flow-heading h1')).to_contain_text('Present')
    page.go_back()
    expect(search).to_have_value('Present')
    expect(page.locator('.material-test-link')).to_have_count(1)
    checks.append('update:library-filter-empty-reset-refresh-back')

    page.goto(base + '/?view=materials')
    page.get_by_role('link', name='Создать тест', exact=True).click()
    expect(page.locator('#test-title')).to_be_visible()
    for width in (320, 390, 768, 1440):
        capture('create', width)
    page.locator('#test-title').fill('Практика — времена английского языка')
    page.locator('#test-subject').select_option(str(subject_id))
    with page.expect_response(lambda r: '/api/task/quick-create/' in r.url and r.request.method == 'POST') as response:
        page.get_by_role('button', name='Создать и добавить вопросы').click()
    assert response.value.status == 201, response.value.text()
    task_id = response.value.json()['id']
    expect(page.get_by_label('Вопрос', exact=True)).to_be_visible()
    page.get_by_label('Вопрос', exact=True).fill('Choose the correct sentence:')
    page.get_by_label('Вариант 1', exact=True).fill('She has already finished her homework.')
    page.get_by_label('Вариант 2', exact=True).fill('She have already finished her homework.')
    page.locator('.correct-choice-label input').first.check()
    for width in (320, 390, 768, 1440):
        capture('editor', width)
    with page.expect_response(lambda r: '/api/question/' in r.url and r.request.method == 'POST') as response:
        page.locator('.editor-actions .btn-primary').click()
    assert response.value.status == 201, response.value.text()
    expect(page.locator('.flow-question-button')).to_have_count(1)
    page.reload()
    expect(page.locator('.flow-question-button')).to_have_count(1)
    page.set_viewport_size({'width': 390, 'height': 1000})
    page.locator('.flow-question-button').click()
    expect(page.locator('.flow-editor-head h2')).to_be_focused()
    expect(page.get_by_label('Вопрос', exact=True)).to_have_value('Choose the correct sentence:')
    page.locator('.flow-back').click()
    expect(page.locator('.flow-question-list h2')).to_be_focused()
    page.locator('.flow-question-button').click()
    page.get_by_label('Вопрос', exact=True).fill('Несохранённая формулировка')
    page.locator('.page-breadcrumbs a').first.click()
    expect(page.get_by_role('dialog')).to_be_visible()
    page.keyboard.press('Escape')
    expect(page.get_by_label('Вопрос', exact=True)).to_have_value('Несохранённая формулировка')
    page.get_by_label('Вопрос', exact=True).fill('Choose the correct sentence:')
    checks.append('update:create-save-reload-mobile-focus-unsaved-guard')

    page.locator('.workspace-tabs').get_by_role('button', name='Назначение', exact=True).click()
    expect(page.locator('.workspace-tabs .active')).to_have_text('Назначение')
    page.locator('.assignment-fields select').select_option(str(group_id))
    page.locator('.assignment-fields input').fill((timezone.localdate() + timedelta(days=1)).isoformat())
    for width in (320, 390, 768, 1440):
        capture('assign', width)
    page.route(f'**/api/task/{task_id}/assign/', lambda route: route.fulfill(status=503, json={'detail': 'Temporary assignment error'}))
    page.get_by_role('button', name='Подтвердить назначение').click()
    expect(page.locator('.assignment-panel [role="alert"]')).to_be_visible()
    expect(page.get_by_role('heading', name='Тест назначен', exact=True)).to_have_count(0)
    page.unroute(f'**/api/task/{task_id}/assign/')
    with page.expect_response(lambda r: '/assign/' in r.url and r.request.method == 'POST') as response:
        page.get_by_role('button', name='Подтвердить назначение').click()
    assert response.value.status == 201, response.value.text()
    expect(page.get_by_role('heading', name='Тест назначен', exact=True)).to_be_visible()
    page.get_by_role('link', name='Открыть расписание', exact=True).click()
    expect(page.locator('.group-page')).to_be_visible()
    checks.append('update:assign-error-retry-real-api-schedule')

    page.route('**/api/task/?*', lambda route: route.fulfill(status=503, json={'detail': 'Temporary library error'}))
    page.goto(base + '/?view=materials')
    expect(page.get_by_role('heading', name='Не удалось загрузить тесты')).to_be_visible()
    page.unroute('**/api/task/?*')
    page.get_by_role('button', name='Повторить', exact=True).click()
    expect(page.locator('.material-test-link').first).to_be_visible()
    checks.append('update:library-error-retry')

    csrf = next(c['value'] for c in page.context.cookies() if c['name'] == 'csrftoken')
    for n in range(22):
        result = page.context.request.post(base + '/api/task/quick-create/',
            data={'subject': subject_id, 'title': f'Pagination fixture {n + 1:02}'},
            headers={'X-CSRFToken': csrf})
        assert result.status == 201, result.text()
    page.goto(base + f'/?view=materials&q=Pagination&subject={subject_id}')
    expect(page.locator('.material-test-link')).to_have_count(20)
    page.get_by_role('button', name='Далее', exact=True).click()
    expect(page.locator('.material-test-link')).to_have_count(2)
    page.reload()
    expect(page.locator('.material-test-link')).to_have_count(2)
    expect(page.locator('.material-pagination')).to_contain_text('Страница 2')
    page.locator('.material-test-link').first.click()
    expect(page.locator('.flow-heading h1')).to_contain_text('Pagination')
    page.locator('.page-breadcrumbs a').first.click()
    expect(search).to_have_value('Pagination')
    expect(page.get_by_role('combobox', name='Предмет', exact=True)).to_have_value(str(subject_id))
    expect(page.locator('.material-pagination')).to_contain_text('Страница 2')
    expect(page.locator('.material-test-link')).to_have_count(2)
    checks.append('update:breadcrumb-restores-search-subject-page')
    search.fill('Практика')
    expect(page.locator('.material-test-link')).to_have_count(1)
    expect(page.locator('.material-pagination')).to_have_count(0)
    checks.append('update:real-pagination-refresh-filter-resets-page')
