#!/usr/bin/env python3

# sign_pipeline.py
import argparse
import base64
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec


def main() -> None:
    parser = argparse.ArgumentParser(description='Digitally sign a JSON file with an ECDSA key.')
    parser.add_argument(
        '-p',
        '--private_key',
        default='signing_key.pem',
        help='Path to PEM signing key (default: signing_key.pem)',
    )
    parser.add_argument(
        '-f',
        '--json_file',
        default='build_and_deploy_vanguard.json',
        help='Path to JSON file to sign (default: build_and_deploy_vanguard.json)',
    )
    parser.add_argument(
        '-s',
        '--signature_file',
        default=None,
        help='Path to write base64 signature (default: <json_file>.sig)',
    )
    args = parser.parse_args()

    json_path = Path(args.json_file)
    if args.signature_file is None:
        args.signature_file = str(json_path.with_suffix(json_path.suffix + '.sig'))

    with open(args.private_key, 'rb') as f:
        private_key = serialization.load_pem_private_key(f.read(), password=None)

    with open(args.json_file, 'rb') as f:
        raw = f.read()

    signature = private_key.sign(raw, ec.ECDSA(hashes.SHA256()))

    with open(args.signature_file, 'wb') as f:
        f.write(base64.b64encode(signature))

    print(f'Signed {args.json_file!r} -> {args.signature_file!r}.')


if __name__ == '__main__':
    main()
