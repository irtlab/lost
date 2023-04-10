

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
