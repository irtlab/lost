import lxml.objectify
from urllib import request as http
from lxml.etree import Element, SubElement
from . import MIME_TYPE, LOST_NAMESPACE, NAMESPACE_MAP, GML_NAMESPACE, SRS_URN
from .geometry import Point
from .errors import LoSTError, ServerError


class LoSTClient:
    '''LoST responder implementation

    The LoST responder is an entity that receives queries forwarded to it by
    LoST servers. The responder resolves those queries to local resources.
    '''
    def __init__(self, server_url):
        self.server_url = server_url

    def POST(self, data=None, mime_type=MIME_TYPE):
        req = http.Request(self.server_url, method='POST')
        req.add_header('Content-Type', mime_type)

        with http.urlopen(req, data=data) as res:
            status = res.getcode()
            if status < 200 or status > 299:
                raise ServerError(f'Unsupported HTTP status code: {status}')

            headers = res.info()
            ctype = headers.get('Content-Type', None).split(';')[0].lower()
            if ctype != MIME_TYPE:
                raise ServerError(f'Unsupported Content-Type: {ctype}')

            return res.read()

    def submit(self, data):
        lxml.objectify.deannotate(data, cleanup_namespaces=True, xsi_nil=True)
        xml = lxml.etree.tostring(data, encoding='UTF-8', pretty_print=True, xml_declaration=True)

        res = self.POST(xml)
        try:
            doc = lxml.objectify.fromstring(res)
        except lxml.etree.XMLSyntaxError as e:
            raise ServerError(f'XML syntax error: {e}') from e

        LoSTError.raise_for_errors(doc)

        if not doc.tag.startswith(f'{{{LOST_NAMESPACE}}}'):
            raise ServerError('Unsupported XML namespace')

        return doc

    def findService(self, service: str, location: Point, recursive=True, reference=False):
        doc = Element(f'{{{LOST_NAMESPACE}}}findService',
            nsmap=NAMESPACE_MAP,
            serviceBoundary="reference" if reference else "value",
            recursive="true" if recursive else "false")

        loc = SubElement(doc, 'location', profile="geodetic-2d")
        SubElement(doc, 'service').text = service

        point = SubElement(loc, f'{{{GML_NAMESPACE}}}Point', srsName=SRS_URN)
        SubElement(point, f'{{{GML_NAMESPACE}}}pos').text = f'{location.lat} {location.lon}'

        res = self.submit(doc)

        type_ = res.tag[len(LOST_NAMESPACE) + 2:]
        if type_ != 'findServiceResponse':
            raise ServerError(f'Unexpected response type "{type_}"')

        return [uri.text for uri in res.mapping.uri]
