
MIME_TYPE      = 'application/lost+xml'
LOST_NAMESPACE = 'urn:ietf:params:xml:ns:lost1'
GML_NAMESPACE  = 'http://www.opengis.net/gml'
XML_NAMESPACE  = 'http://www.w3.org/XML/1998/namespace'
SRS_URN        = 'urn:ogc:def:crs:EPSG::4326'

NAMESPACE_MAP  = {
    None: LOST_NAMESPACE,
    'gml': GML_NAMESPACE,
    'xml': XML_NAMESPACE
}

class LoSTResolver:
    '''LoST resolver service implementation

    This class implements a LoST resolver, i.e., a service used by applications
    (clients) to submit queries. The resolver could be running on the same host
    as the application, e.g., in the form of a background process that
    communicates with the application via an inter-process communication channel
    (DBus). It could be also provided as local network service, e.g., as part of
    cloud services provided to applications running on the cloud infrastructure.
    '''
    pass


class LoSTPublisher:
    '''LoST publisher implementation

    A LoST publisher publishes available services and resources on behalf of a
    system. The system could be a PSAP answering 911 calls, or some other
    system, e.g., a cyber-physical system.
    '''
    pass


class LoSTResponder:
    '''LoST responder implementation

    The LoST responder is an entity that receives queries forwarded to it by
    LoST servers. The responder resolves those queries to local resources.
    '''
    pass
