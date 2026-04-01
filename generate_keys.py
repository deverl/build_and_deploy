#!/usr/bin/env python3

# generate_keys.py
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization


def main() -> None:
    private_key = ec.generate_private_key(ec.SECP256R1())

    # Save private key (keep this secret, off the target machine)
    with open('signing_key.pem', 'wb') as f:
        f.write(
            private_key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),  # or add a passphrase
            )
        )

    # Save public key (embed this in your app or deploy alongside it)
    with open('verifying_key.pem', 'wb') as f:
        f.write(
            private_key.public_key().public_bytes(
                serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
            )
        )


if __name__ == '__main__':
    main()
