"""Fail-closed curl downloads, cached only within one build."""
import subprocess

class Downloader:
    def __init__(self) -> None:
        self.cache: dict[str, str] = {}

    def __call__(self, url: str) -> str:
        if not url.startswith('https://'):
            raise ValueError(f'Only HTTPS sources are supported: {url}')
        if url not in self.cache:
            result = subprocess.run([
                'curl', '-L', '--fail', '--silent', '--show-error', '--compressed',
                '--proto', '=https', '--proto-redir', '=https', '--retry', '3',
                '--retry-delay', '2', '--connect-timeout', '15', '--max-time', '120', url,
            ], capture_output=True, check=True)
            text = result.stdout.decode('utf-8-sig')
            if not text.strip():
                raise ValueError(f'Empty download: {url}')
            self.cache[url] = text
        return self.cache[url]
