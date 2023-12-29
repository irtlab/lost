import os
from werkzeug.exceptions  import NotFound
from flask                import send_from_directory, Blueprint

dir = os.path.dirname(__file__)
frontend_dir = os.path.join(dir, 'frontend', 'public')

js = Blueprint('js', __name__)

@js.route('/')
@js.route('/<path:path>')
def serve_frontend(path='index.html'):
    try:
        return send_from_directory(frontend_dir, path)
    except NotFound:
        return send_from_directory(frontend_dir, 'index.html')
