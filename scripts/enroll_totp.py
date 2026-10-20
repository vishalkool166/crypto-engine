#!/usr/bin/env python3
"""Enroll an operator authenticator on the private server terminal."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import os
import pyotp
from dotenv import dotenv_values, set_key

root=Path(__file__).resolve().parents[1]
target=root/'.env'
if not target.is_file():
    raise SystemExit('Create the private .env first using scripts/setup_env.py')
if not sys.stdout.isatty():
    raise SystemExit('Run interactively on a private terminal; enrollment data is secret')
values=dotenv_values(target)
if values.get('TOTP_SECRET'):
    raise SystemExit('TOTP_SECRET is already configured; enrollment refuses to overwrite it')
secret=pyotp.random_base32()
set_key(str(target),'TOTP_SECRET',secret)
os.chmod(target,0o600)
email=(values.get('ADMIN_EMAILS') or 'operator').split(',')[0]
print('Import this secret or otpauth URI into your authenticator privately. Do not share it.')
print('Secret:',secret)
print(pyotp.TOTP(secret).provisioning_uri(name=email,issuer_name='Signal Engine'))
print('Restart the backend to load the secret. Redis must be connected for step-up operations.')
