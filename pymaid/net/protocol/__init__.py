import abc

from typing import Any, TypeVar

from pymaid.types import DataType


class Protocol(abc.ABC):
    '''pymaid use Protocol representation app protocol layer

    You can build your protocol upon Protocol
    and you can easily change the underlying Protocol

    Build your AppProtocol inherit from Http and change to Http2 if wanted,
    and in best case, do not need to do anything else

    .. code-block:: python

        class AppProtocol(Http):
            ...

        class AppProtocol(Http2):
            ...

    '''

    @abc.abstractclassmethod
    def feed_data(cls, data: DataType):
        raise NotImplementedError

    @abc.abstractclassmethod
    def encode(cls, obj: Any) -> DataType:
        raise NotImplementedError

    @abc.abstractclassmethod
    def decode(cls, data: DataType) -> Any:
        raise NotImplementedError


ProtocolType = TypeVar('Protocol', bound=Protocol)
