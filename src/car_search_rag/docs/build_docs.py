"""Build static docs without importing the app or reading local credentials."""
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
PATTERNS = {
    'private key': re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    'API token': re.compile(r'\b(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|sb_secret_[A-Za-z0-9_-]{16,})'),
    'JWT': re.compile(r'\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}'),
    'connection URL': re.compile(r'\b(?:postgres(?:ql)?(?:\+[\w]+)?|mysql|redis)://[^\s<>"\x27]+', re.I),
    'URL credentials': re.compile(r'https?://[^\s/:]+:[^\s/@]+@', re.I),
    'secret assignment': re.compile(r'\b(?:DB_URL|OPENAI_API_KEY|SUPABASE_URL|SUPABASE_SECRET_KEY|API_KEY|PASSWORD|ACCESS_TOKEN)\s*[=:]\s*["\x27]?[^\s"\x27<>`]{8,}', re.I),
}
TEXT = {'.rst', '.py', '.css', '.html', '.js', '.json', '.txt', '.map', '.svg'}


def scan(directory):
    issues = []
    for path in sorted(directory.rglob('*')):
        if path.is_file() and path.suffix in TEXT:
            content = path.read_text(encoding='utf-8')
            for label, pattern in PATTERNS.items():
                if pattern.search(content):
                    issues.append(f'{path.relative_to(directory)}: {label}')
    if issues:
        # Never print matched values, even on failure.
        raise RuntimeError('Sensitive content detected: ' + '; '.join(issues))


def main():
    build = ROOT / 'build'
    build.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='docs-', dir=build) as temporary:
        stage = Path(temporary)
        source = stage / 'source'
        source.mkdir()
        # Explicit allowlist: no .env, application code, old screenshots or raw diagrams.
        for name in ('conf.py', 'index.rst', 'getting_started.rst', 'development_guide.rst',
                     'project_structure.rst', 'sql_mapper_guide.rst', 'api.rst', 'security.rst'):
            shutil.copy2(ROOT / 'source' / name, source / name)
        (source / '_public').mkdir()
        shutil.copy2(ROOT / 'source/_public/custom.css', source / '_public/custom.css')
        scan(source)
        output = stage / 'html'
        result = subprocess.run([sys.executable, '-m', 'sphinx', '-b', 'html', '-n', '-W',
                                 '--keep-going', '-d', str(stage / 'doctrees'), str(source), str(output)],
                                capture_output=True, text=True)
        if result.returncode:
            # Sphinx diagnostics may echo source lines: keep them out of public logs.
            raise RuntimeError('Sphinx validation failed; review the documentation source locally.')
        scan(output)
        if any(path.is_file() for path in (output / '_sources').rglob('*')):
            raise RuntimeError('Unexpected source copies in output')
        target = build / 'html'
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(output, target)
    print('Documentation built; source and HTML secret-pattern checks passed.')


if __name__ == '__main__':
    try:
        main()
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
