from typing import TypeVar

ConnectionType = TypeVar('Connection')

Request = TypeVar('Request')
Response = TypeVar('Response')

Context = TypeVar('Context')
InboundContext = TypeVar('InboundContext', bound=Context)
OutboundContext = TypeVar('OutboundContext', bound=Context)
Method = TypeVar('Method')
MethodStub = TypeVar('MethodStub')

RouterType = TypeVar('Router')
ServiceType = TypeVar('Service')
