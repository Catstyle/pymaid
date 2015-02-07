from .base import Error

module_index = 10000


class ServiceNotExist(Error):

    code = module_index + 1
    message_format = '[service|{service_name}] not found'


class MethodNotExist(Error):

    code = module_index + 2
    message_format = '[service|{service_name}][method|{method_name}] not found'


class ParserNotExist(Error):

    code = module_index + 3
    message_format = '[parser|{parser_type}] not found'


class HeartbeatTimeout(Error):

    code = module_index + 4
    message_format = '[host|{host}][peer|{peer}] peer heartbeat timeout'
