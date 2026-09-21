import base64
import difflib
import hashlib
import importlib.util
import socket
import threading
import html
import json
import os
import shutil
import mimetypes
import re
import subprocess
import sys
import tempfile
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
import unicodedata
import warnings
import webbrowser
import zipfile
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath


from ls_core.runtime import APP_DIR
from ls_core.assets import asset_text, asset_url

STATIC_PREFIX = '/ls-static/'
STATIC_ROOT = APP_DIR

_MIME = {'.css':'text/css; charset=utf-8','.js':'application/javascript; charset=utf-8','.ico':'image/x-icon','.png':'image/png','.html':'text/html; charset=utf-8','.json':'application/json; charset=utf-8'}

def read_static_asset(url_path):
    raw=url_path.split('?',1)[0]
    if not raw.startswith(STATIC_PREFIX): return None
    rel=urllib.parse.unquote(raw[len(STATIC_PREFIX):]).replace('\\','/')
    pp=PurePosixPath(rel)
    if pp.is_absolute() or '..' in pp.parts: return None
    path=(APP_DIR / Path(*pp.parts)).resolve()
    if APP_DIR.resolve() not in path.parents or not path.is_file(): return None
    # Public static routing is deliberately narrower than the application root:
    # templates, Python sources, manifests and user data are never downloadable.
    if 'static' not in pp.parts or path.suffix.lower() not in {'.css', '.js', '.ico', '.png'}:
        return None
    mime=_MIME.get(path.suffix.lower(), mimetypes.guess_type(str(path))[0] or 'application/octet-stream')
    return path.read_bytes(), mime
