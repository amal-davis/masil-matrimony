"""
Settings are split per environment:

- base.py         shared configuration, read from environment variables
- development.py  local development (DEBUG on, permissive localhost CORS)
- production.py   hardened production (DEBUG off, HTTPS, secure cookies)
- test.py         automated test runs

Select one with DJANGO_SETTINGS_MODULE, e.g. config.settings.development.
"""
