"""PyInstaller entry point - uses absolute imports."""

import os
import sys

# Ensure urllib/ssl can find CA certificates in PyInstaller bundles.
# Without this, urllib.request fails with SSL: CERTIFICATE_VERIFY_FAILED
# because the bundled Python cannot locate the system CA store.
_cert = "/etc/ssl/cert.pem"
if os.path.isfile(_cert):
    os.environ.setdefault("SSL_CERT_FILE", _cert)


def main():
    from wenzi.app import main as app_main
    app_main()


if __name__ == "__main__":
    from wenzi.scripting.ocr import _OCR_WORKER_FLAG
    if _OCR_WORKER_FLAG in sys.argv:
        from wenzi.scripting.ocr import _main as ocr_main
        ocr_main()
    else:
        main()
