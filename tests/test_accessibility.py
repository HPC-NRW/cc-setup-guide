"""Offline accessibility regressions used by test_docs.py --browser.

Automated rules and keyboard/reflow checks complement manual image descriptions,
screen-reader review and usability testing; they are not a conformance certificate.
"""
import pathlib
import re
import urllib.parse


AXE_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa', 'best-practice']


def settle_layout(page):
    page.evaluate('() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))')


def axe_scan(page):
    return page.evaluate('''async tags => {
      const result = await axe.run(document, {runOnly:{type:'tag', values:tags}});
      const compact = rule => ({id:rule.id, impact:rule.impact, help:rule.help,
        helpUrl:rule.helpUrl, nodes:rule.nodes.map(n => ({target:n.target, summary:n.failureSummary}))});
      return {version:axe.version, violations:result.violations.map(compact),
        incomplete:result.incomplete.map(compact), passed_rules:result.passes.length};
    }''', AXE_TAGS)


def audit_page(page, relative, axe_script):
    """Check the rendered document and both supported color schemes."""
    expected_language = None if relative == '404.html' else 'de' if relative.startswith('de/') else 'en'
    facts = page.evaluate('''() => {
      const article = document.querySelector('article');
      const headings = [...article.querySelectorAll('h1,h2,h3,h4,h5,h6')]
        .map(e => ({level:Number(e.tagName.slice(1)), text:e.textContent.trim()}));
      const images = [...article.querySelectorAll('img')].map(e => ({
        src:e.getAttribute('src'), alt:e.getAttribute('alt'),
        decorative:e.getAttribute('role') === 'presentation' || e.getAttribute('aria-hidden') === 'true'
      }));
      return {lang:document.documentElement.lang, headings, images};
    }''')
    failures = []
    if facts['lang'] not in ('de', 'en') or expected_language and facts['lang'] != expected_language:
        failures.append('incorrect document language: ' + facts['lang'])
    if relative == '404.html':
        # i18n writes a shared fallback page using its final build locale.
        phrase = 'nicht gefunden' if facts['lang'] == 'de' else 'not found'
        if not any(phrase in heading['text'].lower() for heading in facts['headings']):
            failures.append('fallback error heading does not match its declared language')
    if sum(h['level'] == 1 for h in facts['headings']) != 1:
        failures.append('article must have one descriptive page heading')
    previous = 0
    for heading in facts['headings']:
        if not heading['text'] or heading['level'] > previous + 1:
            failures.append('empty heading or skipped heading level: ' + heading['text'])
        previous = heading['level']
    for image in facts['images']:
        if not image['decorative'] and not (image['alt'] or '').strip():
            failures.append('informative image lacks alternative text: ' + image['src'])
        if image['alt'] and re.fullmatch(r'[^/\s]+\.(png|jpe?g|svg|webp)', image['alt'].strip(), re.I):
            failures.append('image alternative is a filename: ' + image['src'])
    page.add_script_tag(path=str(axe_script))
    schemes = []
    for scheme in ['default', 'slate']:
        page.evaluate('(scheme) => document.body.setAttribute("data-md-color-scheme", scheme)', scheme)
        settle_layout(page)
        result = axe_scan(page)
        result['scheme'] = scheme
        schemes.append(result)
        failures.extend(scheme + ': ' + violation['id'] for violation in result['violations'])
    page.set_viewport_size({'width': 320, 'height': 900})
    settle_layout(page)
    overflow = page.evaluate('''() => ({
      viewport:document.documentElement.clientWidth,
      page:document.documentElement.scrollWidth,
      containers:[...document.querySelectorAll('article *')].filter(e => {
        const s=getComputedStyle(e);
        return e.clientWidth > 0 && e.scrollWidth > e.clientWidth + 1 && /auto|scroll/.test(s.overflowX);
      }).map(e => ({tag:e.tagName, cls:e.className, focusable:e.tabIndex >= 0,
        name:e.getAttribute('aria-label') || e.getAttribute('aria-labelledby') || '',
        hasControl:!!e.querySelector('a[href],button,input,select,textarea,[tabindex="0"]')}))
    })''')
    if overflow['page'] > overflow['viewport'] + 1:
        failures.append('page overflows horizontally at 320 CSS pixels')
    for container in overflow['containers']:
        if not container['focusable'] and not container['hasControl']:
            failures.append('scrollable content is unreachable by keyboard: ' + container['tag'] + '.' + str(container['cls']))
        elif container['focusable'] and not container['name']:
            failures.append('focusable scrollable content lacks a name: ' + container['tag'] + '.' + str(container['cls']))
    page.set_viewport_size({'width': 1440, 'height': 1050})
    settle_layout(page)
    return {'path':relative, 'document':facts, 'schemes':schemes, 'mobile':overflow, 'failures':failures}


def keyboard_checks(page, base, axe_script=None, checks=None):
    """Exercise navigation that must work without a pointer."""
    checks = [] if checks is None else checks
    axe_script = axe_script or pathlib.Path(__file__).parent / 'vendor/axe-core/axe.min.js'

    def open_state(name, language):
        if not page.evaluate('typeof axe !== "undefined"'):
            page.add_script_tag(path=str(axe_script))
        state = {'language':language, 'opened_state':name, 'schemes':[]}
        checks.append(state)
        for scheme in ['default', 'slate']:
            page.evaluate('(scheme) => document.body.setAttribute("data-md-color-scheme", scheme)', scheme)
            settle_layout(page)
            result = axe_scan(page)
            result['scheme'] = scheme
            state['schemes'].append(result)
    for language, relative in [('en', ''), ('de', 'de/')]:
        page.goto(base + relative, wait_until='networkidle')
        page.keyboard.press('Tab')
        skip = page.locator(':focus')
        assert skip.count() == 1 and (skip.get_attribute('href') or '').startswith('#'), 'First Tab must expose the skip-to-content link'
        assert skip.is_visible() and skip.inner_text().strip(), 'Skip link must be visible and named on focus'
        page.keyboard.press('Enter')
        page.keyboard.press('Tab')
        assert page.locator(':focus').evaluate('(e) => !!e.closest("main")'), 'Skip link must move keyboard navigation past the site header'
        checks.append({'language':language, 'skip_link':'PASS'})
        page.goto(base + relative + 'https_setup/', wait_until='networkidle')
        summary = page.locator('article summary').first
        summary.focus()
        page.keyboard.press('Enter')
        assert summary.evaluate('(e) => e.parentElement.open'), 'Enter must open the configuration disclosure'
        page.keyboard.press('Space')
        assert not summary.evaluate('(e) => e.parentElement.open'), 'Space must close the configuration disclosure'
        checks.append({'language':language, 'disclosure_keyboard':'PASS'})
        page.set_viewport_size({'width':320, 'height':900})
        page.goto(base + relative, wait_until='networkidle')
        menu = page.locator('.md-header button[data-guide-toggle="__drawer"]')
        menu.focus()
        page.keyboard.press('Enter')
        settle_layout(page)
        assert menu.get_attribute('aria-expanded') == 'true', 'Enter must open mobile navigation'
        assert page.locator(':focus').evaluate('(e) => !!e.closest(".md-sidebar--primary")'), 'Opening navigation must focus the visible drawer'
        for key in ['Tab', 'Shift+Tab']:
            page.keyboard.press(key)
            assert page.locator(':focus').evaluate('(e) => !!e.closest(".md-sidebar--primary")'), 'Modal navigation must keep focus out of the obscured page'
        submenu = page.locator('.md-sidebar--primary button.md-nav__link').filter(visible=True).first
        state = submenu.get_attribute('aria-expanded')
        submenu.focus()
        page.keyboard.press('Enter')
        assert submenu.get_attribute('aria-expanded') != state, 'Enter must toggle a mobile navigation section'
        open_state('mobile navigation with expanded section', language)
        page.keyboard.press('Space')
        settle_layout(page)
        assert submenu.get_attribute('aria-expanded') == state, 'Space must toggle a mobile navigation section'
        page.keyboard.press('Escape')
        settle_layout(page)
        assert menu.get_attribute('aria-expanded') == 'false', 'Escape must close mobile navigation'
        assert menu.evaluate('(e) => e === document.activeElement'), 'Closing navigation must restore its trigger focus'
        menu.focus()
        page.keyboard.press('Space')
        settle_layout(page)
        assert menu.get_attribute('aria-expanded') == 'true', 'Space must open mobile navigation'
        page.keyboard.press('Escape')
        settle_layout(page)
        assert menu.get_attribute('aria-expanded') == 'false', 'Escape must close mobile navigation after either activation key'
        search_button = page.locator('.md-header__button[data-guide-toggle="__search"]')
        search_button.focus()
        page.keyboard.press('Enter')
        settle_layout(page)
        search = page.locator('input[data-md-component="search-query"]')
        page.wait_for_function('document.activeElement === document.querySelector("input[data-md-component=search-query]")', timeout=5000)
        search.press_sequentially('Metrik' if language == 'de' else 'metric', delay=50)
        page.wait_for_function('document.querySelectorAll("[data-md-component=search-result] a").length>0')
        open_state('mobile search with results', language)
        links = page.locator('[data-md-component="search-result"] a').evaluate_all('(els) => els.map(e => e.href)')
        assert links and all(link.startswith(base) for link in links), 'Search results must point into the guide'
        documents = {urllib.parse.urlunsplit((*urllib.parse.urlsplit(link)[:3], '', '')) for link in links}
        for document in documents:
            assert page.context.request.get(document).status == 200, 'Search result points to a missing document: ' + document
        for _ in range(10):
            page.keyboard.press('Tab')
            assert page.locator(':focus').evaluate('(e) => !!e.closest(".md-search[role=dialog]")'), 'Modal search must keep focus out of the obscured page'
        # Material deliberately removes result links from the Tab sequence:
        # ArrowDown/ArrowUp move between the query and the result links.
        search.focus()
        page.keyboard.press('ArrowDown')
        assert page.locator(':focus').evaluate('(e) => !!e.closest("[data-md-component=search-result]")'), 'ArrowDown must reach a search result'
        target = page.locator(':focus').get_attribute('href')
        assert target and target.startswith(base), 'Keyboard result must point into this guide'
        page.keyboard.press('ArrowUp')
        assert page.locator(':focus').evaluate('(e) => !!e.closest(".md-search[role=dialog]")'), 'Arrow navigation must keep focus in search'
        page.keyboard.press('Escape')
        settle_layout(page)
        assert search_button.get_attribute('aria-expanded') == 'false', 'Escape must close search'
        assert search_button.evaluate('(e) => e === document.activeElement'), 'Closing search must restore its trigger focus'
        page.keyboard.press('Enter')
        page.wait_for_function('document.activeElement === document.querySelector("input[data-md-component=search-query]")', timeout=5000)
        page.keyboard.press('ArrowDown')
        assert page.locator(':focus').get_attribute('href') == target, 'Reopened search must retain its keyboard result'
        page.keyboard.press('Enter')
        page.wait_for_url(target)
        checks.append({'language':language, 'mobile_navigation_and_search':'PASS'})
        page.goto(base + relative + 'example_profiles/', wait_until='networkidle')
        # Reference configurations are intentionally collapsed on this page.
        # Reveal them through the keyboard before checking horizontal scrolling.
        for summary in page.locator('article details > summary').all():
            summary.focus()
            page.keyboard.press('Enter')
            assert summary.evaluate('(e) => e.parentElement.open')
        settle_layout(page)
        for selector in ['.md-typeset__scrollwrap', 'pre > code']:
            candidates = page.locator('article ' + selector)
            scrolling = None
            for index in range(candidates.count()):
                candidate = candidates.nth(index)
                if candidate.evaluate('(e) => e.clientWidth > 0 && e.scrollWidth > e.clientWidth + 1'):
                    scrolling = candidate
                    break
            assert scrolling is not None, 'The fixture must contain a wide table and code block'
            scrolling.focus()
            position = scrolling.evaluate('(e) => e.scrollLeft')
            page.keyboard.press('ArrowRight')
            page.wait_for_function('(args) => document.querySelectorAll(args.selector)[args.index].scrollLeft > args.position',
                                   arg={'selector':'article '+selector, 'index':index, 'position':position})
        checks.append({'language':language, 'table_and_code_arrow_scroll':'PASS'})
        page.set_viewport_size({'width':1440, 'height':1050})
    violations = [(state['language'], state['opened_state'], scheme['scheme'], rule['id'])
                  for state in checks if 'opened_state' in state
                  for scheme in state['schemes'] for rule in scheme['violations']]
    assert not violations, f'Opened navigation/search accessibility violations: {violations}'
    return checks
