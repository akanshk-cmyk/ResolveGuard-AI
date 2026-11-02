"""Decrypt a local review package; password is read privately from the terminal."""
import argparse
import base64
import getpass
import hashlib
import json
from pathlib import Path


def decrypt_package(package,password):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
    if package.get('schema')!='resolveguard-export-v1' or package.get('kdf')!='scrypt-n16384-r8-p1':raise ValueError('Unsupported export schema')
    salt=base64.b64decode(package['salt'],validate=True);nonce=base64.b64decode(package['nonce'],validate=True)
    if len(salt)!=16 or len(nonce)!=12:raise ValueError('Invalid export envelope')
    key=Scrypt(salt=salt,length=32,n=2**14,r=8,p=1).derive(password.encode())
    raw=AESGCM(key).decrypt(nonce,base64.b64decode(package['ciphertext'],validate=True),b'resolveguard-export-v1')
    if hashlib.sha256(raw).hexdigest()!=package['plaintext_sha256']:raise ValueError('Export integrity mismatch')
    return raw


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True)
    args=p.parse_args();target=Path(args.output)
    if target.exists():raise SystemExit('Output already exists; choose another path')
    raw=decrypt_package(json.loads(Path(args.input).read_text()),getpass.getpass('Export password: '))
    target.write_bytes(raw);print('Verified export decrypted locally. Protect the resulting file.')
