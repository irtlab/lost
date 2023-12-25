from flask import Flask
from flask_cors import CORS
from psycopg_pool import ConnectionPool
from datetime import datetime


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

app = Flask(__name__)
CORS(app)
