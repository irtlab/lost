import lxml.objectify
from urllib import request as http
from lxml.etree import Element, SubElement
from . import MIME_TYPE, LOST_NAMESPACE, NAMESPACE_MAP, GML_NAMESPACE, SRS_URN
from .geometry import Point
from .errors import BadRequest, LoSTError


class LoSTClient:
    '''LoST responder implementation

    The LoST responder is an entity that receives queries forwarded to it by
    LoST servers. The responder resolves those queries to local resources.
    '''
    def __init__(self, server_url):
        self.server_url = server_url


    def findService(self, service: str, location: Point):
        req = http.Request(self.server_url, method='POST')
        req.add_header('Content-Type', MIME_TYPE)

        doc = Element(f'{{{LOST_NAMESPACE}}}findService',
            nsmap=NAMESPACE_MAP, serviceBoundary="value", recursive="true")

        loc = SubElement(doc, 'location', profile="geodetic-2d")
        SubElement(doc, 'service').text = service

        point = SubElement(loc, f'{{{GML_NAMESPACE}}}Point', srsName=SRS_URN)
        SubElement(point, f'{{{GML_NAMESPACE}}}pos').text = f'{location.lat} {location.lon}'

        lxml.objectify.deannotate(doc, cleanup_namespaces=True, xsi_nil=True)
        xml = lxml.etree.tostring(doc, encoding='UTF-8', pretty_print=True, xml_declaration=True)

        with http.urlopen(req, data=xml) as res:
            code = res.getcode()
            if code < 200 or code > 299:
                raise BadRequest('Invalid response code')

            if not res.info()['Content-Type'].startswith(MIME_TYPE):
                raise BadRequest('Unsupported content type')

            try:
                doc = lxml.objectify.fromstring(res.read())
            except lxml.etree.XMLSyntaxError as e:
                raise BadRequest(f'XML syntax error: {e}') from e

        if not doc.tag.startswith(f'{{{LOST_NAMESPACE}}}'):
            raise BadRequest('Unsupported XML namespace')

        type_ = doc.tag[len(LOST_NAMESPACE) + 2:]
        if type_ == 'findServiceResponse':
            return doc.mapping.displayName.text
        elif type_ == 'errors':
            raise LoSTError('')
        else:
            raise LoSTError(f'Unsupported request type "{type_}"')
