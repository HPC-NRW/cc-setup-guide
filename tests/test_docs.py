#!/usr/bin/env python3
"""Build and test the current source tree, including untracked snippets, locally."""
import argparse
import functools
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.parse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from bs4 import BeautifulSoup


def code_blocks(path):
    blocks = re.findall(r'^\s*```[^\n]*\n(.*?)^\s*```\s*$', path.read_text(), re.M | re.S)
    return ['\n'.join(line.rstrip() for line in block.splitlines()
            if line.strip() and not re.match(r'^\s*(#|//)', line)) for block in blocks]


def browser_check(site, work, executable, source):
    from playwright.sync_api import sync_playwright
    from test_accessibility import audit_page, keyboard_checks
    prefix = 'cc-setup-guide'
    webroot = work / 'webroot'
    webroot.mkdir()
    (webroot / prefix).symlink_to(site, target_is_directory=True)

    class Quiet(SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def copyfile(self, source, outputfile):
            try:
                super().copyfile(source, outputfile)
            except (BrokenPipeError, ConnectionResetError):
                # Navigation can cancel an in-flight asset request; page checks still verify loaded content.
                pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Quiet, directory=str(webroot)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f'http://127.0.0.1:{server.server_port}/{prefix}/'
    output = {'pages': [], 'search': [], 'errors': []}
    accessibility = {'engine':'axe-core 4.14.0', 'pages':[], 'keyboard':[]}
    try:
        with sync_playwright() as playwright:
            options = {'headless': True, 'args': ['--no-sandbox'], 'downloads_path': str(work / 'downloads')}
            if executable:
                options['executable_path'] = executable
            browser = playwright.chromium.launch(**options)
            output['browser'] = browser.version
            context = browser.new_context(viewport={'width': 1440, 'height': 1050}, reduced_motion='reduce')
            context.route('**/*', lambda route: route.continue_()
                          if urllib.parse.urlsplit(route.request.url).hostname == '127.0.0.1' else route.abort())
            page = context.new_page()
            page.on('pageerror', lambda error: output['errors'].append(str(error)))
            for html in sorted(site.rglob('index.html')):
                relative = html.parent.relative_to(site).as_posix()
                relative = '' if relative == '.' else relative + '/'
                response = page.goto(base + relative, wait_until='networkidle')
                assert response.status == 200, relative
                german = relative.startswith('de/')
                expected = base + (relative[3:] if german else 'de/' + relative)
                targets = page.locator('a[hreflang="' + ('en' if german else 'de') + '"]').evaluate_all('(els)=>els.map(e=>e.href)')
                assert expected in targets, (relative, expected, targets)
                article = page.locator('article')
                assert '!!! info' not in article.inner_text(), relative
                assert '```' not in article.inner_text(), relative
                images = article.locator('img').evaluate_all('(els)=>els.map(e=>({url:e.src,complete:e.complete,width:e.naturalWidth}))')
                assert all(image['complete'] and image['width'] > 0 for image in images), (relative, images)
                if relative in ('metrics/', 'de/metrics/', 'more_metrics/', 'de/more_metrics/'):
                    assert article.locator('.admonition.info').count() > 0, relative
                if relative == 'de/operation/':
                    assert article.locator('ul > li').count() >= 3, 'German operation list is not rendered'
                accessibility['pages'].append(audit_page(page, relative, source / 'tests/vendor/axe-core/axe.min.js'))
                output['pages'].append({'path': relative, 'switch': expected, 'status': response.status})
                # Actually follow both home and chapter switches, including the real prefix.
                if relative in ('', 'de/', 'cluster_setup/', 'de/cluster_setup/'):
                    page.locator('a[hreflang="' + ('en' if german else 'de') + '"]').first.evaluate('(e)=>e.click()')
                    page.wait_for_url(expected)
                    assert page.url == expected
                if relative in ('metrics/', 'de/operation/'):
                    page.screenshot(path=str(work / (relative.replace('/', '_') + '.png')))
            page.goto(base + '404.html', wait_until='networkidle')
            accessibility['pages'].append(audit_page(page, '404.html', source / 'tests/vendor/axe-core/axe.min.js'))
            keyboard_checks(page, base, source / 'tests/vendor/axe-core/axe.min.js', accessibility['keyboard'])
            for relative, query in (('', 'metric'), ('de/', 'Metrik')):
                page.goto(base + relative, wait_until='networkidle')
                page.wait_for_function('!document.querySelector("input[data-md-component=search-query]").disabled')
                search = page.locator('input[data-md-component="search-query"]')
                search.click()
                search.press_sequentially(query, delay=100)
                page.wait_for_function('document.querySelectorAll("[data-md-component=search-result] a").length>0')
                hits = page.locator('[data-md-component="search-result"] a').evaluate_all('(els)=>els.map(e=>e.href)')
                assert hits and all(link.startswith(base) for link in hits), hits
                output['search'].append({'language': 'de' if relative else 'en', 'query': query, 'hits': hits})
                page.screenshot(path=str(work / ('search-de.png' if relative else 'search-en.png')))
            for relative in ('advanced/', 'de/advanced/'):
                assert context.request.get(base + relative).status == 404, relative
            assert not output['errors'], output['errors']
            accessibility_failures = [item['path'] + ': ' + failure
                                      for item in accessibility['pages'] for failure in item['failures']]
            assert not accessibility_failures, '\n'.join(accessibility_failures) + f'\nEvidence: {work / "accessibility-results.json"}'
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        (work / 'browser-results.json').write_text(json.dumps(output, indent=2) + '\n')
        (work / 'accessibility-results.json').write_text(json.dumps(accessibility, indent=2) + '\n')
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=pathlib.Path, required=True)
    parser.add_argument('--work', type=pathlib.Path, required=True)
    parser.add_argument('--browser', action='store_true')
    parser.add_argument('--browser-executable', help='Use an existing Chromium/Chrome binary; no automatic installation')
    args = parser.parse_args()
    source = args.source.resolve()
    args.work.mkdir(parents=True, exist_ok=True)
    work = pathlib.Path(tempfile.mkdtemp(prefix='docs-', dir=args.work.resolve()))
    site = work / 'site'
    result = subprocess.run([sys.executable, '-m', 'mkdocs', 'build', '--strict', '--site-dir', str(site)],
                            cwd=source, capture_output=True, text=True)
    (work / 'build.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0, f'Strict build failed: {work / "build.log"}'
    pages = {path: BeautifulSoup(path.read_text(), 'html.parser') for path in site.rglob('*.html')}
    failures = []
    references = 0
    for path, soup in pages.items():
        for tag in soup.find_all(href=True) + soup.find_all(src=True):
            value = tag.get('href', tag.get('src'))
            url = urllib.parse.urlsplit(value)
            if url.scheme or url.netloc:
                continue
            references += 1
            decoded = urllib.parse.unquote(url.path)
            if decoded.startswith('/cc-setup-guide/'):
                target = site / decoded[len('/cc-setup-guide/'):]
            elif decoded.startswith('/'):
                failures.append(f'{path.name}: prefix escape {value}')
                continue
            else:
                target = path.parent / decoded if decoded else path
            target = target.resolve()
            if target.is_dir():
                target /= 'index.html'
            if not target.exists():
                failures.append(f'{path.relative_to(site)}: missing {value}')
            elif url.fragment and target in pages and not pages[target].find(id=urllib.parse.unquote(url.fragment)):
                failures.append(f'{path.relative_to(site)}: missing anchor {value}')
    includes = []
    for path in (source / 'docs').rglob('*.md'):
        for include in re.findall(r'--8<--\s+"([^"]+)"', path.read_text()):
            includes.append(include)
            # Snippets may use line selectors after ':'; paths are relative to docs.
            assert (source / 'docs' / include.split(':')[0]).is_file(), (path, include)
    parity = []
    for english in sorted((source / 'docs').rglob('*.en.md')):
        german = english.with_name(english.name.replace('.en.md', '.de.md'))
        assert german.exists(), english
        same = code_blocks(english) == code_blocks(german)
        parity.append({'chapter': english.relative_to(source / 'docs').as_posix()[:-6], 'code_equal': same})
        if not same:
            failures.append(f'DE/EN code blocks differ: {english.name[:-6]}')
    assert not (source / 'docs/.more_metrics.de.md.swp').exists(), 'Tracked editor residue remains'
    assert not (site / 'advanced').exists() and not (site / 'de/advanced').exists(), 'Author notes were published'
    index = json.loads((site / 'search/search_index.json').read_text())
    assert not any(re.search(r'(^|/)advanced(/|$)', entry['location']) for entry in index['docs']), 'Author notes are searchable'
    locations = [entry['location'] for entry in index['docs']]
    assert len(locations) == len(set(locations)), 'Search index contains duplicate locations'
    parents = set(locations)
    orphan_sections = [location for location in locations if '#' in location and location.split('#', 1)[0] not in parents]
    assert not orphan_sections, 'Search sections lack document parents: ' + repr(orphan_sections)
    assert (site / 'scripts/generate-subcluster.pl').is_file(), 'Helper download missing'
    report = {'html_pages': len(pages), 'references': references, 'includes': includes, 'languages': parity, 'failures': failures}
    (work / 'static-results.json').write_text(json.dumps(report, indent=2) + '\n')
    if args.browser:
        browser_check(site, work, args.browser_executable, source)
    assert not failures, '\n'.join(failures) + f'\nEvidence: {work}'
    print(f'PASS: strict build, {len(pages)} HTML pages, {references} links, {len(includes)} includes, {len(parity)} language pairs' + ('; browser/switch/search/accessibility passed' if args.browser else '') + f'; evidence: {work}')


if __name__ == '__main__':
    main()
