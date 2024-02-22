import lxml.objectify
import lxml.etree
from urllib import request as http
from lxml.etree import Element, SubElement
from . import LOST_MIME_TYPE, LOST_NAMESPACE, NAMESPACE_MAP, GML_NAMESPACE, SRS_URN
from .geometry import Point
from .errors import LoSTError, ServerError


class LoSTClient:
    '''LoST responder implementation

    The LoST responder is an entity that receives queries forwarded to it by
    LoST servers. The responder resolves those queries to local resources.
    '''
    def __init__(self, resolver_url):
        self.resolver_url = resolver_url

    def POST(self, data=None, mime_type=LOST_MIME_TYPE):
        req = http.Request(self.resolver_url, method='POST')
        req.add_header('Content-Type', mime_type)

        with http.urlopen(req, data=data) as res:
            status = res.getcode()
            if status < 200 or status > 299:
                raise ServerError(f'Unsupported HTTP status code: {status}')

            headers = res.info()
            ctype = headers.get('Content-Type', None).split(';')[0].lower()
            if ctype != LOST_MIME_TYPE:
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

    def find(self, service: str, location: lxml.etree._Element, reqTag, resTag, recursive=True, reference=False):
        doc = Element(f'{{{LOST_NAMESPACE}}}{reqTag}',
            nsmap=NAMESPACE_MAP,
            serviceBoundary="reference" if reference else "value",
            recursive="true" if recursive else "false")

        loc = SubElement(doc, 'location', profile="geodetic-2d")
        loc.insert(0, location)
        SubElement(doc, 'service').text = service

        res = self.submit(doc)

        type_ = res.tag[len(LOST_NAMESPACE) + 2:]
        if type_ != resTag:
            raise ServerError(f'Unexpected response type "{type_}"')

        return [uri.text for uri in res.mapping.uri]

    def findService(self, service: str, location: lxml.etree._Element, recursive=True, reference=False):
        doc = Element(f'{{{LOST_NAMESPACE}}}findService',
            nsmap=NAMESPACE_MAP,
            serviceBoundary="reference" if reference else "value",
            recursive="true" if recursive else "false")

        loc = SubElement(doc, 'location', profile="geodetic-2d")
        loc.insert(0, location)
        SubElement(doc, 'service').text = service

        res = self.submit(doc)

        type_ = res.tag[len(LOST_NAMESPACE) + 2:]
        if type_ != 'findServiceResponse':
            raise ServerError(f'Unexpected response type "{type_}"')

        return [uri.text for uri in res.mapping.uri]

    def findIntersect(self, service: str, obj: lxml.etree._Element, recursive=True, reference=False):
        doc = Element(f'{{{LOST_NAMESPACE}}}findIntersect',
            nsmap=NAMESPACE_MAP,
            serviceBoundary="reference" if reference else "value",
            recursive="true" if recursive else "false")

        interest = SubElement(doc, 'interest', profile="geodetic-2d")
        interest.insert(0, obj)
        SubElement(doc, 'service').text = service

        res = self.submit(doc)

        type_ = res.tag[len(LOST_NAMESPACE) + 2:]
        if type_ != 'findIntersectResponse' and type_ != 'findIntersectResponses':
            raise ServerError(f'Unexpected response type "{type_}"')
        
        if type_ == 'findIntersectResponse':
            return [uri.text for uri in res.mapping.uri]
        
        uris = []
        if type_ == 'findIntersectResponses':
            for response in res.findall('.//{{{}}}findIntersectResponse'.format(LOST_NAMESPACE)):
                uri_element = response.find('.//{{{}}}uri'.format(LOST_NAMESPACE))
                if uri_element is not None:
                    uris.append(uri_element.text)
            return uris
        