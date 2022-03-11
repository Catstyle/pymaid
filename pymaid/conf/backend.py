from orjson import loads, dumps

from pymaid.core import create_task
from pymaid.utils.logger import logger_wrapper


def formatter(*formats):
    def wrapper(func):
        func.formats = formats
        return func
    return wrapper


class BackendMeta(type):

    def __new__(cls, name, bases, attrs):
        cls = type.__new__(cls, name, bases, attrs)
        cls.formatters = {}
        for attr in cls.__dict__.keys():
            attr = getattr(cls, attr)
            for format in getattr(attr, 'formats', []):
                cls.formatters[format] = attr
        return cls


class SettingsBackend(metaclass=BackendMeta):

    def __init__(self):
        self.listening = False
        self.fetching = False
        self.subscriptions = {}

    def subscribe(self, ns, settings, format='json'):
        if format not in self.formatters:
            self.logger.warn(
                '[pymaid][settings|%s] subscribed with unknown [format|%s]',
                settings, format
            )
            return False

        if ns in self.subscriptions:
            self.logger.warn(
                '[pymaid][settings|%s] already subscribed with [ns|%s]',
                settings, ns
            )
            return False
        else:
            self.subscriptions[ns] = {'settings': settings, 'format': format}
            return True

    def start(self):
        self.listening = True
        self.worker = create_task(self.run())

    async def run(self):
        raise NotImplementedError('run')

    def stop(self):
        self.listening = False
        if hasattr(self, 'worker'):
            self.worker.kill()


@logger_wrapper(name='pymaid.ApolloBackend')
class ApolloBackend(SettingsBackend):

    def __init__(self,
                 app_id,
                 cluster='default',
                 config_server='http://localhost:8080',
                 timeout=65,
                 api_type='cached'):
        super(ApolloBackend, self).__init__()
        self.config_server = config_server
        self.app_id = app_id
        self.cluster = cluster
        self.timeout = timeout
        self.api_type = api_type
        import requests
        self.session = requests.Session()

    def subscribe(self, ns, settings, format='json'):
        result = super(ApolloBackend, self).subscribe(ns, settings, format)
        if result:
            self.subscriptions[ns]['notificationId'] = -1
            if self.listening and not self.fetching:
                self.stop()  # stop terminate listerner
                self.start()  # start listerner again
        return result

    async def run(self):
        import requests
        while self.listening:
            notifications = [
                {
                    'namespaceName': f'{ns}.{sub["format"]}',
                    'notificationId': sub['notificationId'],
                }
                for ns, sub in self.subscriptions.items()
            ]
            try:
                resp = self.session.get(
                    f'{self.config_server}/notifications/v2',
                    params={
                        'appId': self.app_id,
                        'cluster': self.cluster,
                        'notifications': dumps(notifications),
                    },
                    timeout=self.timeout,
                )
            except requests.exceptions.RequestException as ex:
                self.logger.warn(
                    '[pymaid][settings][backend|%s] raise request error: %r',
                    self.__class__.__name__, ex
                )
                continue

            if resp.status_code == 304:
                self.logger.debug(
                    '[pymaid][settings][backend|%s] no changes, continue',
                    self.__class__.__name__,
                )
                continue

            if resp.ok:
                update = resp.json()
                self.logger.debug(
                    '[pymaid][settings][backend|%s] receive [update|%r]',
                    self.__class__.__name__, update
                )
                self.fetching = True
                delta = {}
                if self.api_type == 'cached':
                    get_data = self.get_cached_data
                else:
                    get_data = self.get_uncached_data
                for item in update:
                    ns = item['namespaceName'].rsplit('.', 1)[0]
                    nid = item['notificationId']
                    if data := get_data(ns, self.subscriptions[ns]['format']):
                        self.subscriptions[ns]['notificationId'] = nid
                        delta[ns] = data

                for ns, data in delta.items():
                    settings = self.subscriptions[ns]['settings']
                    settings.load_from_object(data, ns)
                self.logger.debug(
                    '[pymaid][settings][backend|%s] updated [delta|%r]',
                    self.__class__.__name__, delta.keys()
                )
                self.fetching = False

    def get_cached_data(self, ns, format):
        import requests
        try:
            resp = self.session.get(
                f'{self.config_server}/configfiles/json/'
                f'{self.app_id}/{self.cluster}/{ns}.{format}',
                timeout=self.timeout,
            )
        except requests.exceptions.RequestException as ex:
            self.logger.warn(
                '[pymaid][settings][backend|%s] raise request error: %r',
                self.__class__.__name__, ex
            )
        else:
            if resp.ok:
                return ApolloBackend.formatters[format](self, resp.json())

    def get_uncached_data(self, ns, format):
        import requests
        try:
            resp = self.session.get(
                f'{self.config_server}/configs/'
                f'{self.app_id}/{self.cluster}/{ns}.{format}',
                timeout=self.timeout,
            )
        except requests.exceptions.RequestException as ex:
            self.logger.warn(
                '[pymaid][settings][backend|%s] raise request error: %r',
                self.__class__.__name__, ex
            )
        else:
            if resp.ok:
                return ApolloBackend.formatters[format](
                    self, resp.json()['configurations']
                )

    @formatter('json')
    def json_formatter(self, content):
        return loads(content['content'])

    @formatter('properties')
    def properties_formatter(self, content):
        return content

    @formatter('yaml', 'yml')
    def yaml_formatter(self, content):
        import yaml
        return yaml.load(content['content'])

    @formatter('xml')
    def xml_formatter(self, content):
        import xmltodict
        return xmltodict.parse(content['content'])
