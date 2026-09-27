"""Standard byte-mode QR at ECC L, with mandatory decode verification."""
from pathlib import Path
import qrcode
from qrcode.exceptions import DataOverflowError
from PIL import Image
import zxingcpp

MAX_BYTES = 2953 # Version 40, byte mode, L.

def verify(path: Path, text: str) -> None:
    with Image.open(path) as img:
        result = zxingcpp.read_barcode(img.convert('RGB'))
    if result is None or result.bytes != text.encode('utf-8'):
        raise ValueError('QR decode does not match routing.json bytes')

def generate(path: Path, text: str) -> bool:
    path.unlink(missing_ok=True)
    if len(text.encode('utf-8')) > MAX_BYTES:
        print('routing.json 超过单二维码容量；请从剪贴板导入 routing.json')
        return False
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=8, border=4)
    qr.add_data(text.encode('utf-8'), optimize=0)
    try:
        qr.make(fit=True)
    except DataOverflowError:
        print('routing.json 超过单二维码容量；不生成二维码')
        return False
    qr.make_image(fill_color='black', back_color='white').save(path)
    verify(path, text)
    return True
