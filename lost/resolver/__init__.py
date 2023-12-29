from flask        import Flask
from psycopg_pool import ConnectionPool


class LoSTResolver:
    '''LoST resolver service implementation

    This class implements a LoST resolver, i.e., a service used by applications
    (clients) to submit queries. The resolver could be running on the same host
    as the application, e.g., in the form of a background process that
    communicates with the application via an inter-process communication channel
    (DBus). It could be also provided as local network service, e.g., as part of
    cloud services provided to applications running on the cloud infrastructure.
    '''
    def __init__(self, db: ConnectionPool, root_server):
        self.db = db
        self.root_server = root_server


resolver: LoSTResolver = None


def create_app(frontend, backend, image_dir):
    app = Flask(__name__)

    if frontend:
        from . import frontend
        app.register_blueprint(frontend.js)

    if backend:
        from . import backend
        from werkzeug.exceptions import HTTPException
        from marshmallow import ValidationError

        # There appears to be no way to set URL parameter converters and custom
        # JSON providers on a blueprint.
        app.url_map.converters['guid'] = backend.GUIDFlaskParameter
        app.json = backend.CustomJSONProvider(app)

        # Custom error handlers only seem to work correctly in all cases when
        # they are set on the main application, not on the blueprint.
        app.register_error_handler(HTTPException, backend.handle_error)
        app.register_error_handler(ValidationError, backend.failed_validation)

        app.config['image_dir'] = image_dir
        app.register_blueprint(backend.api, url_prefix='/api')

        app.register_blueprint(backend.images, url_prefix='/image')

    return app