(function(global, factory) {
    global['pymaid'] = factory();
})(this, function() {
    var pymaid = {};

    var pb = pymaid.pb = {};
    var pbJson = {
        "package": "pymaid.pb",
        "messages": [
            {
                "name": "Controller",
                "fields": [
                    {
                        "rule": "optional",
                        "type": "string",
                        "name": "service_method",
                        "id": 1
                    },
                    {
                        "rule": "optional",
                        "type": "PacketType",
                        "name": "packet_type",
                        "id": 2
                    },
                    {
                        "rule": "optional",
                        "type": "uint32",
                        "name": "transmission_id",
                        "id": 3
                    },
                    {
                        "rule": "optional",
                        "type": "bool",
                        "name": "is_canceled",
                        "id": 4
                    },
                    {
                        "rule": "optional",
                        "type": "bool",
                        "name": "is_failed",
                        "id": 5
                    }
                ],
                "enums": [
                    {
                        "name": "PacketType",
                        "values": [
                            {
                                "name": "UNKNOWN",
                                "id": 0
                            },
                            {
                                "name": "REQUEST",
                                "id": 1
                            },
                            {
                                "name": "RESPONSE",
                                "id": 2
                            },
                            {
                                "name": "NOTIFICATION",
                                "id": 3
                            }
                        ]
                    }
                ]
            },
            {
                "name": "Void",
                "fields": []
            },
            {
                "name": "ErrorMessage",
                "fields": [
                    {
                        "rule": "optional",
                        "type": "uint32",
                        "name": "error_code",
                        "id": 1
                    },
                    {
                        "rule": "optional",
                        "type": "string",
                        "name": "error_message",
                        "id": 2
                    }
                ]
            }
        ]
    };
    var builder = dcodeIO.ProtoBuf.loadJson(pbJson).build('pymaid');
    pb.Controller = builder.pb.Controller;
    pb.Void = builder.pb.Void;
    pb.ErrorMessage = builder.pb.ErrorMessage;


    /**
     * Channel, implement rpc pack/unpack
     *
    **/
    var Channel = function(connectionClass) {
        this.connectionClass = connectionClass;
        this.conn = null;
        this.listener = null;
        this.isConnected = false;
        this.transmissionId = 0;
        this.transmissions = {};
    };

    var ChannelPrototype = Object.create(Channel.prototype);
    Channel.prototype = ChannelPrototype;
    pymaid.Channel = Channel;

    // 5 is for '!BHH'
    ChannelPrototype._headerSize = 5;

    ChannelPrototype._packPacket = function(controller, content) {
        var ctrlSize = controller.calculate();
        var contentSize = content.calculate();

        var bb = new dcodeIO.ByteBuffer(this._headerSize + ctrlSize + contentSize);
        bb.writeUint8(1); // protobuf
        bb.writeUint16(ctrlSize);
        bb.writeUint16(contentSize);
        bb.append(controller.toBuffer());
        bb.append(content.toBuffer());
        bb.flip();
        return bb.toBuffer();
    };

    ChannelPrototype._unpackPacket = function(ab) {
        var bb = dcodeIO.ByteBuffer.wrap(ab);
        var type = bb.readUint8();

        var ctrlSize = bb.readUint16();
        var contentSize = bb.readUint16();

        var ctrlLimit = this._headerSize + ctrlSize;
        var controllerBuf = bb.slice(this._headerSize, ctrlLimit);
        var controller = pb.Controller.decode(controllerBuf);

        var contentBuf = null;
        if (contentSize) {
            contentBuf = bb.slice(ctrlLimit, ctrlLimit + contentSize);
        }

        return {controller: controller, content: contentBuf};
    };

    ChannelPrototype.bindListener = function(listener) {
        if (this.listener) {
            cc.warn('already bound listener: ' + this.listener);
            return;
        }
        this.listener = listener;
    };

    ChannelPrototype.connect = function(urlpath, cb) {
        if (this.conn && !this.conn.isClosed) {
            cc.warn('channel connection already connected');
            return;
        }
        this.conn = new this.connectionClass(urlpath, this);
        this.openCB = cb;
    };

    ChannelPrototype.sendRequest = function(method, request, cb) {
        var controller = new pb.Controller({
            service_method: method,
            packet_type: pb.Controller.PacketType.REQUEST,
            transmission_id: this.transmissionId++
        });
        this.conn.send(this._packPacket(controller, request));
        this.transmissions[method] = cb
    };

    ChannelPrototype.sendResponse = function(controller, response) {
        this.conn.send(this._packPacket(controller, response));
    };

    ChannelPrototype.close = function() {
        this.conn.close();
    };

    ChannelPrototype.onopen = function(evt) {
        cc.log('channel opened');
        this.isConnected = true;
        if (this.openCB) {
            this.openCB(this, evt);
        }
    };

    ChannelPrototype.onclose = function(evt) {
        cc.log('channel closed');
        this.isConnected = false;
    };

    ChannelPrototype.onmessage = function(evt) {
        var packet = this._unpackPacket(evt.data);
        var controller = packet.controller, content = packet.content;
        if (controller.packet_type == pb.Controller.PacketType.RESPONSE) {
            this.onresponse(controller, content);
        } else {
            this.listener.onmessage(this, controller, content);
        }
    };

    ChannelPrototype.onresponse = function(controller, content) {
        var method = controller.service_method;
        var cb = this.transmissions[method];
        if (!cb) {
            cc.error('method: ' + method + 'has no cb');
            // what to do?
            return;
        }
        cb(controller, content);
    };

    ChannelPrototype.onerror = function(evt) {
    };


    /**
     * WSConnection, connection wrapper for websocket
     *
    **/
    var WSConnection = function(urlpath, channel) {
        this.ws = new WebSocket(urlpath);
        this.ws.binaryType = 'arraybuffer';
        this.channel = channel;

        this.ws.onopen = this.onopen.bind(this);
        this.ws.onclose = this.onclose.bind(this);
        this.ws.onmessage = this.onmessage.bind(this);
        this.ws.onerror = this.onerror.bind(this);

        this.isClosed = true;
    };

    var WSConnectionPrototype = Object.create(WSConnection.prototype);
    WSConnection.prototype = WSConnectionPrototype;
    pymaid.WSConnection = WSConnection;

    WSConnectionPrototype.send = function(buf) {
        this.ws.send(buf);
    };

    // avoid `this` pollution
    WSConnectionPrototype.onopen = function(evt) {
        this.channel.onopen(evt);
        this.isClosed = false;
    };

    WSConnectionPrototype.onclose = function(evt) {
        this.channel.onclose(evt);
        this.isClosed = true;
    };

    WSConnectionPrototype.onmessage = function(evt) {
        this.channel.onmessage(evt);
    };

    WSConnectionPrototype.onerror = function(evt) {
        this.channel.onerror(evt);
    };


    /**
     * Listener, used for service implementation
     *
    **/
    var Listener = function() {
        this.classes = {};
        this.implementations = {};
    };

    var ListenerPrototype = Object.create(Listener.prototype);
    Listener.prototype = ListenerPrototype;
    pymaid.Listener = Listener;

    ListenerPrototype._registerService = function(service) {
        var serviceName = service.fqn();
        var rpc = service.getChildren(dcodeIO.ProtoBuf.Reflect.Service.RPCMethod);
        for (var idx = 0; idx < rpc.length; ++idx) {
            var method = rpc[idx], serviceMethod = method.fqn();
            var impl = this.implementations[serviceName][method.name];
            cc.assert(impl && impl.constructor.name == 'Function',
                      'implementations has no method: ' + method.name);
            // '.package.service.method' vs 'package.service.method'
            this.classes[serviceMethod] = this.classes[serviceMethod.slice(1)]= {
                req: method.resolvedRequestType.clazz,
                resp: method.resolvedResponseType.clazz
            };
        }
    };

    ListenerPrototype._iterBuilderResult = function(result) {
        for (var name in result) {
            var attr = result[name];
            if (attr.$type instanceof dcodeIO.ProtoBuf.Reflect.Service) {
                this._registerService(attr.$type);
            } else if (attr.$type instanceof dcodeIO.ProtoBuf.Reflect.Namespace) {
                this._iterBuilderResult(attr);
            }
        }
    };

    ListenerPrototype.registerImpl = function(impl) {
        this.implementations[impl.name] = this.implementations['.'+impl.name] = impl;
    };

    ListenerPrototype.registerBuilder = function(builder) {
        if (!builder.resolved) {
            builder.build();
        }
        this._iterBuilderResult(builder.result);
    };

    ListenerPrototype.onmessage = function(channel, controller, content) {
        var serviceMethod = controller.service_method;
        var dot = serviceMethod.lastIndexOf('.');
        var serviceName = serviceMethod.substr(0, dot);
        var methodName = serviceMethod.substr(dot+1);

        var impl = this.implementations[serviceName];
        if (!impl || !impl[methodName]) {
            this.onNoSuchImpl(serviceMethod);
            return;
        }
        var clazz = this.classes[serviceMethod];
        impl[methodName](controller, clazz.req.decode(content), function(err, content) {
            if (clazz.resp.name == 'Void') {
                // failed silently when handle notification
                return;
            }
            controller.packet_type = pb.Controller.PacketType.RESPONSE;
            if (err) {
                controller.is_failed = true;
                channel.sendResponse(controller, new pb.ErrorMessage(err));
            } else {
                if (content === null) {
                    throw Error('impl:' + serviceMethod + ' cb got null content');
                }
                if (!(content instanceof clazz.resp)) {
                    content = new clazz.resp(content);
                }
                channel.sendResponse(controller, content);
            }
        });
    };

    ListenerPrototype.onNoSuchImpl = function(serviceMethod) {
        cc.warn('listener has no such impl: ' + serviceMethod);
    };


    /**
     * Stub, used for client side services stubs
     *
    **/
    var Stub = function(ch) {
        this.channel = ch;
    };

    var StubPrototype = Object.create(Stub.prototype);
    Stub.prototype = StubPrototype;
    pymaid.Stub = Stub;

    StubPrototype._cbWrapper = function(cb) {
        var wrapper = function(controller, content) {
            var err = null;
            if (controller.is_failed) {
                err = pb.ErrorMessage.decode(content);
            }
            cb(err, content);
        };
        return wrapper;
    };

    StubPrototype.rpc = function(method, req, cb) {
        this.channel.sendRequest(method, req, this._cbWrapper(cb));
    };

    StubPrototype.registerStub = function(stub) {
        var name = stub.$type.name;
        name = name[0].toLowerCase() + name.slice(1);
        this[name] = new stub(this.rpc.bind(this));
    };


    /**
     * HttpManager, used to handle cookies/redirect things
     *
    **/
    var HttpManager = function() {
        this._rootUrl = '';
        this._cookies = '';
    };

    var HMPrototype = HttpManager.prototype = Object.create(HttpManager.prototype);
    pymaid.HttpManager = HttpManager;

    HMPrototype._realUrl = function(url) {
        if (url.startsWith('http://') || url.startsWith('https://')) {
            return url;
        }
        return this._rootUrl + url;
    };

    HMPrototype.setRootUrl = function(url) {
        if (!(url.startsWith('http://')) && !(url.startsWith('https://'))) {
            url = 'http://' + url;
        }
        if (url.endsWith('/')) {
            url = url.substr(0, url.length-1);
        }
        this._rootUrl = url;
    };

    HMPrototype.setCookies = function(cookies) {
        if (cookies) {
            var cookies = cookies.split(',');
            for (var idx in cookies) {
                var cookie = cookies[idx].trim().split(';')[0];
                if (cookie.startsWith('sessionid')) {
                    cc.log('HttpManager setCookies: ' + cookie);
                    this._cookies = cookie;
                    break;
                }
            }
        }
    };

    HMPrototype.onNotAuthenticated = function() {
        cc.log('HttpManager became not authenticated');
    };

    HMPrototype.newRequest = function(type, url, cb, async) {
        var async = async || true;
        var self = this;

        var req = cc.loader.getXMLHttpRequest();
        req.open(type.toUpperCase(), this._realUrl(url), async);
        req.setRequestHeader('Cookie', this._cookies);

        req.onreadystatechange = function() {
            if (req.readyState != 4) {
                return;
            }
            self.setCookies(req.getResponseHeader('Set-Cookie'));

            var status = req.status;
            var response = req.responseText;

            if (status >= 200 && status <= 207) {
                try {
                    var obj = JSON.parse(response);
                } catch (e) {
                    if (e instanceof SyntaxError) {
                        cb({code: 1, message: 'invalide json response', status: status}, response);
                    } else {
                        throw e;
                    }
                }
                cb(null, obj);
            } else if (status == 301 || status == 302) {
                var location = req.getResponseHeader('Location').trim();
                if (!location.endsWith('/')) {
                    location += '/';
                }
                self.get(location, '', cb);
            } else if (status == 401 || status == 403) {
                self.onNotAuthenticated();
            } else {
                cb({code: 2, message: req.statusText, status: status}, response);
            }
        };

        req.onerror = function() {
            cb({code: 3, message: 'http request onerror', status: req.status});
        };

        return req;
    };

    HMPrototype.get = function(url, data, cb) {
        var data = data || '';
        var req = this.newRequest('GET', url, cb);
        req.send(data);
        return req;
    };

    HMPrototype.post = function(url, data, cb) {
        var data = JSON.stringify(data) || '';
        var req = this.newRequest('POST', url, cb);
        req.setRequestHeader("Content-Type", "application/json; charset=UTF-8");
        req.send(data);
        return req;
    };

    return pymaid;
});
