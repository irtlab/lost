
MIME_TYPE      = 'application/lost+xml'
LOST_NAMESPACE = 'urn:ietf:params:xml:ns:lost1'
GML_NAMESPACE  = 'http://www.opengis.net/gml'
XML_NAMESPACE  = 'http://www.w3.org/XML/1998/namespace'
SRS_URN        = 'urn:ogc:def:crs:EPSG::4326'

# This is a namespace map passed as a parameter passed to the various lxml
# function. It declares all the XML namespaces used in LoST XML documents.
NAMESPACE_MAP  = {
    None: LOST_NAMESPACE,
    'gml': GML_NAMESPACE,
    'xml': XML_NAMESPACE
}


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
