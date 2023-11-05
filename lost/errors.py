import sys
import inspect
import lxml.objectify
from lxml.etree import Element, SubElement
from . import NAMESPACE_MAP, LOST_NAMESPACE, XML_NAMESPACE


class LoSTError(Exception):
    '''An abstract LoST protocol error
    '''
    type = 'error'

    def __init__(self, message: str | None = None):
        self.message = message

    def to_xml(self, source=None):
        res = Element(f'{{{LOST_NAMESPACE}}}errors', nsmap=NAMESPACE_MAP)
        err = SubElement(res, self.type)

        if self.message is not None:
            err.set('message', self.message)

        if source is not None:
            err.set('source', source)

        err.set(f'{{{XML_NAMESPACE}}}lang', 'en')
        return res

    @classmethod
    def raise_for_errors(cls, errors: lxml.objectify.ObjectifiedElement):
        if errors.tag != f'{{{LOST_NAMESPACE}}}errors':
            return

        error = errors.getchildren()[0]
        type_ = error.tag[len(LOST_NAMESPACE) + 2:]
        message = error.attrib.get('message', None)

        for _, cls in inspect.getmembers(sys.modules[__name__], inspect.isclass):
            if cls.__base__ is LoSTError and cls.type == type_:
                raise cls(message)

        raise LoSTError(message)


class BadRequest(LoSTError):
    '''The LoST server could not understand the request

     The server could not parse or otherwise understand a request, e.g., because
     the XML was malformed.
    '''
    type = 'badRequest'


class Forbidden(LoSTError):
    '''The LoST server refused to process the request

    The server refused to send an answer. This generally only occurs for
    recursive queries, namely, if the client tried to contact the authoritative
    server and was refused.
    '''
    type = 'forbidden'


class InternalError(LoSTError):
    '''Internal error on the LoST server

     The server could not satisfy a request due to misconfiguration or other
     operational and non-protocol-related reasons.
    '''
    type = 'internalError'


class LocationProfileUnrecognized(LoSTError):
    '''None of the location profiles were recognized

     None of the profiles in the request were recognized by the server.
    '''
    type = 'locationProfileUnrecognized'


class LocationInvalid(LoSTError):
    '''Invalid location information

     The geodetic or civic location in the request was invalid. For example, the
     longitude or latitude values fall outside the acceptable ranges
    '''
    type = 'locationInvalid'


class SRSInvalid(LoSTError):
    '''Invalid spatial reference system (SRS) id

     The spatial reference system (SRS) contained in the location element was
     not recognized or does not match the location profile.
    '''
    type = 'SRSInvalid'


class Loop(LoSTError):
    '''Loop detected during recursive LoST query

     During a recursive query, the server was about to visit a server that was
     already in the server list in the <path> element, indicating a request
     loop.
    '''
    type = 'loop'


class NotFound(LoSTError):
    '''No answer found

    The server could not find an answer to the query.
    '''
    type = 'notFound'


class ServerError(LoSTError):
    '''Could not parse response from another LoST server

     An answer was received from another LoST server, but it could not be parsed
     or otherwise understood. This error occurs only for recursive queries.
    '''
    type = 'serverError'


class ServerTimeout(LoSTError):
    '''A LoST server timed out

    A time out occurred before an answer was received.
    '''
    type = 'serverTimeout'


class NotAuthoritative(LoSTError):
    '''The LoST server is not authoritative for the request

    The LoST server received a request that falls outside its area of
    responsibility and refuses to process it.
    '''
    type = 'notAuthoritative'


class NotImplemented(LoSTError):
    '''Feature is not implemented'''
    type = 'notImplemented'


class ServiceNotImplemented(NotImplemented):
    '''The request service URN is not implemented

     The requested service URN is not implemented and no substitution was
     available.
    '''
    type = 'serviceNotImplemented'


class GeometryNotImplemented(NotImplemented):
    '''GML geometry type is not implemented
    '''
    type = 'geometryNotImplemented'
