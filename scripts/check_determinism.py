"""Build twice from one immutable download snapshot and compare every byte."""
from pathlib import Path
import sys
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from convert import SOURCE, convert
from src.downloader import Downloader

download = Downloader()
text = download(SOURCE)
with tempfile.TemporaryDirectory() as temp:
    first, second = Path(temp) / 'a', Path(temp) / 'b'
    convert(text, download, first)
    convert(text, download, second)
    def snapshot(path):
        return {str(p.relative_to(path)): p.read_bytes() for p in path.rglob('*') if p.is_file()}
    if snapshot(first) != snapshot(second):
        raise ValueError('Nondeterministic output')
print('Determinism: all generated files byte-identical')
