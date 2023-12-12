from datetime import datetime
from hashlib import md5

from flask import Flask, request

app = Flask(__name__)


@app.route('/cache/<int:interval>')
def cache(interval):
    """Cacheable endpoint that uses an ETag that resets every `interval` seconds"""
    now = datetime.now()
    server_etag = md5(str(now.second // interval).encode()).hexdigest()
    request_etag = request.headers.get('If-None-Match')
    if request_etag == server_etag:
        return 'NOT MODIFIED', 304
    else:
        return 'OK', 200, {'ETag': server_etag}
