"""Group scenarios shared by the disposable-DB workstation browser suite."""
import re
from playwright.sync_api import expect


def check_group_workspace(page, base, group_id, empty_group_id, task_id, previous_date, checks, artifacts):
    overview = f'{base}/group/{group_id}/overview'
    details = f'{base}/group/{group_id}/details'

    def tab(label):
        page.get_by_role('navigation', name='Разделы группы').get_by_role('link', name=label, exact=True).click()
        expect(page.locator('.group-tabs [aria-current="page"]')).to_have_count(1)

    page.goto(overview + '?tab=summary')
    expect(page.get_by_role('heading', level=1)).to_have_text('11А')
    expect(page.locator('.group-metric').first.locator('strong')).to_have_text('1')
    for width in [320, 390, 768, 1440]:
        page.set_viewport_size({'width': width, 'height': 1000})
        for label, key in [('Сводка', 'summary'), ('Расписание', 'schedule'), ('Результаты', 'results'), ('Состав', 'members'), ('Настройки', 'settings')]:
            tab(label)
            expect(page.get_by_role('heading', level=1)).to_have_text('11А')
            if key == 'summary':
                expect(page.locator('.metric-subject')).to_contain_text('Английский язык')
                expect(page.locator('.group-metric').nth(1).locator('strong')).not_to_have_text('—')
            if key == 'schedule':
                expect(page.locator('.schedule-day-card')).to_have_count(7)
                page.locator('.schedule-day-card').first.get_by_role('button', name='Назначить / изменить').click()
            if key == 'results':
                expect(page.locator('.member-item')).to_have_count(1)
                date_input = page.get_by_label('Дата результатов', exact=True)
                date_input.fill(previous_date)
                date_input.press('Tab')
                expect(page.locator('.member-results-list a')).to_have_count(1)
            if key == 'members':
                expect(page.locator('.compact-members-list .member-item')).to_have_count(1)
            expect(page.get_by_role('navigation', name='Разделы группы').get_by_role('link', name='Материалы', exact=True)).to_be_visible()
            size = page.evaluate('''() => ({width:innerWidth, page:document.documentElement.scrollWidth,
                overflows:[...document.querySelectorAll('.schedule-day-card,.group-metric,.member-item')]
                .filter(e=>e.getClientRects().length && e.scrollWidth>e.clientWidth+2).map(e=>e.className)})''')
            assert size['page'] <= width + 1 and not size['overflows'], (key, width, size)
            checks.append(f'group:{key}:{width}')
            if width in [390, 1440]:
                page.screenshot(path=str(artifacts / f'group-{key}-{width}.png'), full_page=True)
            if key == 'schedule':
                page.locator('.schedule-day-card.is-editing').get_by_role('button', name='Готово', exact=True).click()
        page.goto(details + '?tab=results')
        expect(page.get_by_role('heading', name='Подробная статистика', exact=True)).to_be_visible()
        expect(page.locator('.statistics-test-title').first).to_be_attached()
        expect(page.get_by_role('navigation', name='Разделы группы').get_by_role('link', name='Материалы', exact=True)).to_be_visible()
        selected_period = page.locator('.statistics-scale-btn.active')
        assert selected_period.evaluate('(e) => getComputedStyle(e).color !== getComputedStyle(e).backgroundColor')
        sort_button = page.locator('.statistics-sort-toggle')
        sort_button.focus()
        assert sort_button.evaluate('(e) => getComputedStyle(e).outlineStyle !== "none"')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), ('statistics', width)
        checks.append(f'group:statistics:{width}')
        if width in [390, 1440]:
            page.screenshot(path=str(artifacts / f'group-statistics-{width}.png'), full_page=True)

    tab('Результаты')
    date_input = page.get_by_label('Дата результатов', exact=True)
    date_input.fill(previous_date)
    date_input.press('Tab')
    expect(page.locator('.member-results-list a')).to_have_count(1)
    page.reload()
    expect(date_input).to_have_value(previous_date)
    page.locator('.member-results-list a').click()
    expect(page.locator('.attempt-page')).to_be_visible()
    page.go_back()
    expect(page.get_by_label('Дата результатов', exact=True)).to_have_value(previous_date)
    checks.append('group:results-date-refresh-open-attempt-back')
    search = page.get_by_role('searchbox', name='Найти студента в группе')
    search.fill('student_fixture')
    expect(page).to_have_url(re.compile('q=student_fixture'))
    page.get_by_role('combobox', name='Сортировать студентов').select_option('rank')
    page.reload()
    expect(search).to_have_value('student_fixture')
    expect(page.get_by_role('combobox', name='Сортировать студентов')).to_have_value('rank')
    search.fill('несуществующий')
    expect(page.locator('.member-item')).to_have_count(0)
    page.get_by_role('button', name='Очистить поиск').click()
    expect(page.locator('.member-item')).to_have_count(1)
    checks.append('group:query-search-sort-refresh-clear')

    tab('Расписание')
    empty_day = page.locator('.schedule-day-card:not(.is-assigned)').last
    empty_day.get_by_role('button', name='Назначить / изменить').click()
    empty_day.get_by_role('combobox', name='Тема', exact=True).select_option(index=1)
    topic_draft = empty_day.get_by_role('combobox', name='Тема', exact=True).input_value()
    tab('Состав')
    tab('Расписание')
    # Wait for activation's last request, so a late refresh cannot mask lost drafts.
    page.wait_for_load_state('networkidle')
    expect(page.locator('.schedule-editor-day.is-editing select').first).to_have_value(topic_draft)
    checks.append('group:topic-only-draft-across-components')
    task_select = empty_day.get_by_role('combobox', name='Тест', exact=True)
    expect(task_select.locator('option')).not_to_have_count(1)
    task_select.select_option(str(task_id))
    tab('Состав')
    tab('Расписание')
    expect(page.locator('.schedule-editor-day.is-editing select').last).to_have_value(str(task_id))
    tab('Результаты')
    tab('Расписание')
    expect(page.locator('.schedule-editor-day.is-editing select').last).to_have_value(str(task_id))
    with page.expect_response(lambda response: '/topic-calendar/' in response.url and response.request.method == 'PATCH') as saved:
        page.locator('.schedule-editor-day.is-editing').get_by_role('button', name='Сохранить', exact=True).click()
    assert saved.value.status in [200, 201]
    expect(page.locator('.schedule-panel [role="status"]')).to_be_visible()
    with page.expect_response(lambda response: '/topic-calendar/' in response.url and response.request.method == 'DELETE') as cleared:
        page.locator('.schedule-editor-day.is-editing').get_by_role('button', name='Очистить', exact=True).click()
    assert cleared.value.status in [200, 204]
    checks.append('group:schedule-draft-tabs-save-clear')

    tab('Состав')
    page.get_by_role('textbox', name='Например, 42 или alex').fill('new_member_fixture')
    expect(page.locator('.search-results .search-item')).to_have_count(1)
    page.locator('.search-results').get_by_role('button', name='Добавить', exact=True).click()
    expect(page.locator('.compact-members-list .member-item')).to_have_count(2)
    added = page.locator('.compact-members-list .member-item').filter(has_text='new_member_fixture')
    added.get_by_role('button', name='Удалить', exact=True).click()
    expect(page.get_by_role('dialog')).to_contain_text('new_member_fixture')
    page.keyboard.press('Escape')
    expect(added.get_by_role('button', name='Удалить', exact=True)).to_be_focused()
    added.get_by_role('button', name='Удалить', exact=True).click()
    page.locator('dialog .btn-primary').click()
    expect(page.locator('.compact-members-list .member-item')).to_have_count(1)
    checks.append('group:member-add-remove-confirm-cancel-focus')

    tab('Настройки')
    subject = page.locator('#group-subject')
    original = subject.input_value()
    subject.select_option('')
    tab('Сводка')
    tab('Настройки')
    expect(subject).to_have_value('')
    tab('Состав')
    tab('Настройки')
    expect(subject).to_have_value('')
    page.get_by_role('button', name='Отменить изменения', exact=True).click()
    expect(subject).to_have_value(original)
    checks.append('group:settings-draft-tabs-reset')
    with page.expect_response(lambda response: '/teacher-assignment/' in response.url and response.request.method == 'PATCH') as assigned:
        page.get_by_role('button', name='Сохранить', exact=True).click()
    assert assigned.value.status == 200
    expect(page.locator('.assignment-panel [role="status"]')).to_be_visible()
    page.get_by_role('button', name='Убрать дисциплину из группы', exact=True).click()
    expect(page.get_by_role('dialog')).to_be_visible()
    page.keyboard.press('Escape')
    expect(subject).to_have_value(original)
    checks.append('group:settings-save-remove-cancel')

    stats_url = f'**/api/group/{group_id}/detailed-statistics/**'
    page.route(stats_url, lambda route: route.fulfill(status=503, json={'detail': 'Synthetic stats error'}))
    page.goto(details + '?tab=results')
    expect(page.locator('.members-panel [role="alert"]')).to_be_visible()
    expect(page.locator('.statistics-table-wrap')).to_have_count(0)
    page.unroute(stats_url)
    page.locator('.members-panel').get_by_role('button', name='Повторить', exact=False).click()
    expect(page.locator('.statistics-table')).to_be_visible()
    checks.append('group:statistics-error-retry-without-false-empty')

    page.goto(f'{base}/group/{empty_group_id}/overview?tab=results')
    expect(page.locator('.members-panel .empty-box')).to_have_text('В группе пока нет студентов.')
    checks.append('group:empty-roster')

    def readonly_group(route):
        response = route.fetch()
        data = response.json()
        data['can_manage_students'] = False
        route.fulfill(response=response, json=data)
    page.route(f'{base}/api/group/{group_id}/', readonly_group)
    page.goto(details + '?tab=members')
    expect(page.locator('.compact-members-list .member-item')).to_have_count(1)
    expect(page.locator('.search-input')).to_have_count(0)
    expect(page.locator('.ghost-danger-btn')).to_have_count(0)
    page.unroute(f'{base}/api/group/{group_id}/')
    checks.append('group:readonly-roster-visibility')
