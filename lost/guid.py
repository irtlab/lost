import uuid
import base64

__all__ = ["GUID"]

class GUID:
    '''A globally unique identifier.

    A custom implementation of a globally unique identifier. Backed by UUID
    version 4 (randomly generated) with a base64 string representation.
    '''
    def __init__(self, *args):
        if len(args) == 0:
            self.value = uuid.uuid4()
        elif len(args) == 1:
            v = args[0]
            if v is None:
                self.value = uuid.uuid4()
            if isinstance(v, uuid.UUID):
                self.value = v
            elif isinstance(v, GUID):
                self.value = v.value
            elif isinstance(v, str):
                if len(v) == 22:
                    self.value = uuid.UUID(bytes=base64.urlsafe_b64decode(f'{v}=='), version=4)
                else:
                    self.value = uuid.UUID('{%s}' % v)
            else:
                raise Exception("Unsupported GUID value representation")
        else:
            raise Exception("Unsupported number of GUID parameters")

    def __str__(self):
        return base64.urlsafe_b64encode(self.value.bytes)[:-2].decode('ascii')

    def __eq__(self, obj):
        return self.value == obj.value
