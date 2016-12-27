(function(global, factory) {
    global['pymaid'] = factory();
})(this, function() {
    var pymaid = {};

    var pb = pymaid.pb = {};
    var pbJson = {
        "syntax": "proto3",
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

    getBuilder = function(pb_json, builders) {
        if (typeof pb_json !== 'object') {
            console.log('registerBuilder got argument is not json/object');
            return;
        }
        if (!pb_json.hasOwnProperty('syntax')) {
            for (var attr in pb_json) {
                if (!pb_json.hasOwnProperty(attr)) {
                    continue;
                }
                getBuilder(pb_json[attr], builders);
            }
            return;
        }
        builders.push(dcodeIO.ProtoBuf.loadJson(pb_json));
    }

    /**
     * Parser, encode/decode packet
     *
     */
    var PBParser = {}, JSONParser = {};
    pymaid.PBParser = PBParser;
    pymaid.JSONParser = JSONParser;

    // 4 is for '!HH'
    PBParser._headerSize = JSONParser._headerSize = 4;

    PBParser.pack = function(controller, content) {
        var ctrlSize = controller.calculate();
        var contentSize = content.calculate();

        var bb = new dcodeIO.ByteBuffer(this._headerSize + ctrlSize + contentSize);
        bb.writeUint16(ctrlSize);
        bb.writeUint16(contentSize);
        bb.append(controller.toBuffer());
        bb.append(content.toBuffer());
        bb.flip();
        return bb.toBuffer();
    };

    PBParser.unpack = function(ab) {
        var bb = dcodeIO.ByteBuffer.wrap(ab);
        var ctrlSize = bb.readUint16();
        var contentSize = bb.readUint16();

        var ctrlLimit = this._headerSize + ctrlSize;
        var controllerBuf = bb.slice(this._headerSize, ctrlLimit);
        var controller = pb.Controller.decode(controllerBuf);

        var contentBuf = bb.slice(ctrlLimit, ctrlLimit + contentSize);
        return {controller: controller, content: contentBuf};
    };

    JSONParser.pack = function(controller, content) {
        var ctrlSize = controller.calculate();
        var contentSize = content.calculate();

        var bb = new dcodeIO.ByteBuffer(this._headerSize + ctrlSize + contentSize);
        bb.writeUint16(ctrlSize);
        bb.writeUint16(contentSize);
        bb.append(controller.encodeJSON());
        bb.append(content.encodeJSON());
        bb.flip();
        return bb.toBuffer();
    };

    JSONParser.unpack = function(ab) {
        var bb = dcodeIO.ByteBuffer.wrap(ab);
        var ctrlSize = bb.readUint16();
        var contentSize = bb.readUint16();

        var controllerBuf = bb.readString(ctrlSize);
        var controller = pb.Controller.decode(JSON.parse(controllerBuf));

        var contentBuf = bb.readString(contentSize);
        return {controller: controller, content: JSON.parse(contentBuf)};
    };


    /**
     * Channel, implement rpc pack/unpack
     *
    **/
    var Channel = function(protos, pbimpl, broadcasts, parser) {
        this.conn = null;
        this.parser = parser || PBParser;
        this.is_closed = true;

        var builders = [];
        getBuilder(protos, builders);
        this.init_stubs(builders);
        this.init_listener(builders, pbimpl, broadcasts);
    };

    var ChannelPrototype = Channel.prototype = Object.create(Channel.prototype);
    pymaid.Channel = Channel;

    ChannelPrototype._combineAddress = function(schema, host, port) {
        var address = host + ':' + port;
        if (schema === 'ws' || schema === 'wss') {
            address = schema + '://' + address;
        }
        return address;
    },

    ChannelPrototype.isAlreadyConnected = function(address) {
        var conn = this.conn;
        if (conn && conn.address === address && !conn.is_closed) {
            return true;
        }
        return false;
    },

    ChannelPrototype.connect = function(schema, host, port, callbacks) {
        var address = this._combineAddress(schema, host, port);
        if (this.isAlreadyConnected(address)) {
            console.log(
                'pymaid: channel already connected to address: ' + address
            );
            return this.conn;
        }

        var self = this;
        channel_callbacks = {
            onopen: function(conn) {
                self.connection_made(conn);
                callbacks.onopen && callbacks.onopen(conn);
            },

            onclose: function(conn, evt) {
                self.connection_closed(conn, evt);
                callbacks.onclose && callbacks.onclose(conn, evt);
            },

            onerror: callbacks.onerror | function() {},
        };
        // now we support websocket only
        return new WSConnection(address, this, channel_callbacks);
    };

    ChannelPrototype.close = function(reason) {
        if (this.is_closed) {
            return;
        }
        console.log('pymaid: channel closing with [reason|' + reason + ']');
        this.is_closed = true;
        this.conn.close(reason);
        this.conn.channel = null;
        this.conn = null;
    };

    ChannelPrototype.connection_made = function(conn) {
        this.conn = conn;
        this.is_closed = false;
        this.stubs.bindConnection(conn);
    };

    ChannelPrototype.connection_closed = function(conn) {
        this.close('connection closed');
        this.stubs.conn = null;
    };

    ChannelPrototype.init_stubs = function(builders) {
        var stubs = this.stubs = new pymaid.StubManager();
        for (var idx = 0, length = builders.length; idx < length; idx++) {
            stubs.registerBuilder(builders[idx]);
        }
    };

    ChannelPrototype.init_listener = function(builders, pbimpl, broadcasts) {
        var listener = this.listener = new pymaid.Listener();
        for (var impl in pbimpl) {
            if (!pbimpl.hasOwnProperty(impl)) {
                continue;
            }
            listener.registerImpl(pbimpl[impl]);
        }

        for (var idx = 0, length = builders.length; idx < length; idx++) {
            listener.registerBuilder(builders[idx], function(name) {
                return broadcasts.indexOf(name) != -1;
            });
        }
    };


    /**
     * WSConnection, connection wrapper for websocket
     *
    **/
    var WSConnection = function(address, channel, callbacks) {
        this.ws = new WebSocket(address);
        this.ws.binaryType = 'arraybuffer';
        this.channel = channel;
        this.parser = channel.parser;

        this.address = address;
        this.connid = WSConnection.CONNID;
        WSConnection.CONNID++;
        this.transmissionId = 0;
        this.transmissions = {};

        var callbacks = callbacks || {};
        this.onopen_callback = callbacks.onopen || function() {};
        this.onerror_callback = callbacks.onerror || function() {};
        this.onclose_callback = callbacks.onclose || function() {};

        this.ws.onopen = this.onopen.bind(this);
        this.ws.onclose = this.onclose.bind(this);
        this.ws.onmessage = this.onmessage.bind(this);
        this.ws.onerror = this.onerror.bind(this);

        this.send = this.ws.send.bind(this.ws);
    };
    WSConnection.CONNID = 0;

    var WSConnectionPrototype = Object.create(WSConnection.prototype);
    WSConnection.prototype = WSConnectionPrototype;
    pymaid.WSConnection = WSConnection;

    WSConnectionPrototype.close = function(reason) {
        console.log(
            'pymaid: [WSConnection|'+this.connid+'][address|'+this.address+']'+
            '[reason|'+reason+'] closed'
        );
        this.ws.close();
        this.cleanup(reason);
    };

    WSConnectionPrototype.cleanup = function(reason) {
        for (var idx in this.transmissions) {
            var cb = this.transmissions[idx];
            cb({error_code: 100, error_message: 'pymaid: rpc conn closed with [reason|' + reason + ']'});
            delete this.transmissions[idx];
        }
    }

    WSConnectionPrototype.onmessage = function(evt) {
        var packet = this.parser.unpack(evt.data);
        var controller = packet.controller, content = packet.content;

        if (controller.packet_type == pb.Controller.PacketType.RESPONSE) {
            var tid = controller.transmission_id;
            var cb = this.transmissions[tid];
            if (!cb) {
                console.log(
                    'pymaid: [WSConnection|'+this.connid+'][transmission|'+tid+']' +
                    '[service_method|'+controller.service_method+'] has no cb'
                );
                // what to do?
                return;
            }
            delete this.transmissions[tid];
            cb(controller, content);
        } else {
            this.channel.listener.onmessage(controller, content, this);
        }
    };

    WSConnectionPrototype.onopen = function(evt) {
        console.log('pymaid: [WSConnection|'+this.connid+'][address|'+this.address+']'+ 'onopen');
        this.is_closed = false;
        this.onopen_callback(this);
    };

    WSConnectionPrototype.onclose = function(evt) {
        console.log('pymaid: [WSConnection|'+this.connid+'][address|'+this.address+']'+ 'onclose');
        this.is_closed = true;
        this.onclose_callback(this, evt);
        this.cleanup(evt);
        // onclose is after onerror, cleanup from here
        this.onopen_callback = null;
        this.onerror_callback = null;
        this.onclose_callback = null;
        this.channel = null;
    };

    WSConnectionPrototype.onerror = function(evt) {
        console.log('pymaid: [WSConnection|'+this.connid+'][address|'+this.address+']'+ 'onerror');
        this.onerror_callback(this, evt);
    };

    var getBuilderServices = function(result, filter) {
        var services = []
        for (var name in result) {
            var attr = result[name];
            if (attr.$type instanceof dcodeIO.ProtoBuf.Reflect.Service) {
                if (filter && !(filter(name))) {
                    continue;
                }
                services.push(attr.$type);
            } else if (attr.$type instanceof dcodeIO.ProtoBuf.Reflect.Namespace) {
                services = services.concat(getBuilderServices(attr, filter));
            } else if (typeof attr === 'object' && Object.keys(attr)) {
                services = services.concat(getBuilderServices(attr, filter));
            }
        }
        return services;
    };


    /**
     * Stub, used for client side services stubs
     *
    **/
    var Stub = function(manager, service) {
        this._manager = manager;
        this._buildRpc(service);
    };

    var StubPrototype = Stub.prototype = Object.create(Stub.prototype);
    pymaid.Stub = Stub;

    StubPrototype._buildRpc = function(service) {
        var rpc = service.$type.getChildren(dcodeIO.ProtoBuf.Reflect.Service.RPCMethod);
        for (var idx in rpc) {
            (function(method) {
                var methodName = method.fqn();
                var requestType = method.resolvedRequestType;
                var responseType = method.resolvedResponseType;

                var requireResponse = responseType.name !== 'Void';
                var illegalResponse = {
                    error_code: 101,
                    error_message: "Illegal response received in: " + methodName
                };

                this[method.name] = function(req, cb, conn) {
                    var conn = conn || this._manager.conn;
                    if (!cb || cb.constructor.name != 'Function') {
                        throw Error(
                            'pymaid: rpc cb is not function: ' + method.name
                        );
                    }
                    if (!conn || conn.is_closed) {
                        cb({error_code: 102, error_message: 'pymaid: rpc conn is null/closed'}, null);
                        return;
                    }

                    var controller = new pb.Controller({
                        service_method: methodName,
                        packet_type: pb.Controller.PacketType.REQUEST,
                    });
                    if (requireResponse) {
                        var tid = conn.transmissionId;
                        controller.transmission_id = tid;
                        conn.transmissionId++;
                    }
                    if (!(req instanceof requestType.clazz)) {
                        req = new requestType.clazz(req);
                    }
                    console.log(
                        'pymaid: [Stub][controller|'+controller.encodeJSON()+']'+
                        '[req|'+req.encodeJSON()+']'
                    );
                    conn.send(conn.parser.pack(controller, req));

                    if (!requireResponse) {
                        setTimeout(cb.bind(this, null, null), 0);
                    } else {
                        conn.transmissions[tid] = function(controller, resp) {
                            var err = null;
                            if (!controller) {
                                err = illegalResponse;
                            } else if (controller.is_failed) {
                                err = pb.ErrorMessage.decode(resp);
                            } else {
                                try {
                                    resp = responseType.clazz.decode(resp);
                                } catch (notABuffer) {
                                }
                                if (!(resp instanceof responseType.clazz)) {
                                    err = illegalResponse;
                                }
                            }
                            console.log(
                                'pymaid: [WSConnection|'+conn.connid+'][address|'+conn.address+']'+
                                '[onmessage][controller|'+controller.encodeJSON()+'][content|'+JSON.stringify(resp)+']'
                            );
                            cb(err, resp);
                        };
                    }
                };
            }).bind(this)(rpc[idx]);
        }
    };


    /**
     * StubManager, manage stubs for services
     *
     */
    var StubManager = function() {
        this.conn = null;
    };

    var StubManagerPrototype = Object.create(StubManager.prototype);
    StubManager.prototype = StubManagerPrototype;
    pymaid.StubManager = StubManager;

    StubManagerPrototype._registerStub = function(stub) {
        var name = stub.name;
        console.log('pymaid: registering stub: ' + name);
        name = name[0].toLowerCase() + name.slice(1);
        this[name] = new Stub(this, stub.clazz);
    };

    StubManagerPrototype.registerBuilder = function(builder) {
        if (!builder.resolved) {
            builder.build();
        }
        var services = getBuilderServices(builder.result);
        for (var idx in services) {
            this._registerStub(services[idx]);
        }
    };

    StubManagerPrototype.bindConnection = function(conn) {
        if (this.conn && !this.conn.is_closed) {
            console.log('pymaid: StubManager already bound connection');
            return;
        }
        this.conn = conn;
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
        console.log('pymaid: listener registering service: ' + serviceName);
        var rpc = service.getChildren(dcodeIO.ProtoBuf.Reflect.Service.RPCMethod);
        for (var idx = 0; idx < rpc.length; ++idx) {
            var method = rpc[idx], serviceMethod = method.fqn();
            var impl = this.implementations[serviceName][method.name];
            if (!impl || impl.constructor.name != 'Function') {
                throw Error('pymaid: listener has no method: ' + method.name);
            }
            // '.package.service.method' and 'package.service.method'
            this.classes[serviceMethod] = this.classes[serviceMethod.slice(1)] = {
                req: method.resolvedRequestType,
                resp: method.resolvedResponseType
            };
        }
    };

    ListenerPrototype.registerImpl = function(impl) {
        this.implementations[impl.name] = this.implementations['.'+impl.name] = impl;
    };

    ListenerPrototype.registerBuilder = function(builder, filter) {
        if (!builder.resolved) {
            builder.build();
        }
        var services = getBuilderServices(builder.result, filter);
        for (var idx in services) {
            this._registerService(services[idx]);
        }
    };

    ListenerPrototype.onmessage = function(controller, content, conn) {
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
        var req = clazz.req.clazz.decode(content), resp = clazz.resp;
        console.log(
            'pymaid: [WSConnection|'+conn.connid+'][address|'+conn.address+']'+
            '[onmessage][controller|'+controller.encodeJSON()+'][content|'+req.encodeJSON()+']'
        );
        impl[methodName](controller, req, function(err, content) {
            if (resp.name == 'Void') {
                // when handle notification
                return;
            }
            controller.packet_type = pb.Controller.PacketType.RESPONSE;
            if (err) {
                controller.is_failed = true;
                conn.send(conn.parser.pack(controller, new pb.ErrorMessage(err)));
            } else {
                if (content === null) {
                    throw Error('pymaid: impl: '+serviceMethod+' got null content');
                }
                if (!(content instanceof resp)) {
                    content = new resp(content);
                }
                conn.send(conn.parser.pack(controller, content));
            }
        });
    };

    ListenerPrototype.onNoSuchImpl = function(serviceMethod) {
        console.log('pymaid: listener has no such impl: ' + serviceMethod);
    };


    /**
     * HttpManager, used to handle cookies/redirect things
     *
    **/
    var HttpManager = function(rootUrl, webimpl, requestClass) {
        this.setRootUrl(rootUrl)
        this._cookies = '';
        requestClass = requestClass || XMLHttpRequest;
        if (!requestClass) {
            throw Error('invalid requestClass for HttpManager');
        }
        this._requestClass = requestClass;

        for (var impl in webimpl) {
            if (!webimpl.hasOwnProperty(impl)) {
                continue;
            }
            cc.log(impl + ' is binding httpManager');
            webimpl[impl].bindHttpManager(this);
        }
        this.webimpl = webimpl;
    };

    var HMPrototype = HttpManager.prototype = Object.create(HttpManager.prototype);
    pymaid.HttpManager = HttpManager;

    var args4Method = function(args) {
        var url = args[0];
        var data = '', cb = null;
        if (args.length == 2) {
            cb = args[1];
        } else if (args.length == 3) {
            data = args[1];
            cb = args[2];
        }
        return [url, data, cb];
    };

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
            // e.g. 'token=xxx; Expires=Thu, 20-Oct-2016 19:58:45 GMT; Path=/, session=yyy; Expires=Fri, 21-Oct-2016 07:58:45 GMT; HttpOnly; Path=/'
            // cookies.split(',') will return 4 elements:
            // ['token=xxx; Expires=Thu', ' 20-Oct-2016 19:58:45 GMT; Path=/', ' session=yyy; Expires=Fri', ' 21-Oct-2016 07:58:45 GMT; HttpOnly; Path=/']
            // but we know what we need will be in the first place
            // so we just need element.trim().split(';')[0]
            // !!!! IT IS A TRICKY HACKY !!!
            var cookies = cookies.split(',');
            var list = [];
            for (var idx in cookies) {
                var cookie = cookies[idx].trim().split(';')[0];
                list.push(cookie);
            }
            this._cookies = list.join('; ');
            console.log('pymaid: HttpManager setCookies: ' + this._cookies);
        }
    };

    HMPrototype.newRequest = function(type, url, cb, async) {
        var async = async || true;
        var self = this;

        var req = new this._requestClass();
        req.withCredentials = true;
        req.open(type.toUpperCase(), this._realUrl(url), async);
        req.setRequestHeader('Cookie', this._cookies);

        req.onreadystatechange = function() {
            if (req.readyState != 4) {
                return;
            }
            self.setCookies(req.getResponseHeader('Set-Cookie'));

            var status = req.status;
            var response = req.responseText;
            var err = null;

            if (status >= 200 && status <= 207) {
                try {
                    response = JSON.parse(response);
                } catch (e) {
                    if (e instanceof SyntaxError) {
                        err = {
                            error_code: 1,
                            error_message: 'invalide json response',
                            status: status
                        };
                    } else {
                        throw e;
                    }
                }
            } else if (status == 301 || status == 302) {
                var location = req.getResponseHeader('Location').trim();
                self.get(location, {}, cb);
                return;
            } else {
                err = {
                    error_code: 2, error_message: req.statusText, status: status
                };
                try {
                    response = JSON.parse(response);
                } catch (e) {
                    if (!(e instanceof SyntaxError)) {
                        throw e;
                    }
                }
            }
            cb(err, response);
        };

        req.onerror = function() {
            cb({error_code: 3, error_message: 'http request onerror',
                status: req.status});
        };

        return req;
    };

    HMPrototype.get = function(url, data, cb) {
        var args = args4Method(arguments);
        var url = args[0], data = args[1] || {}, cb = args[2];
        var attr, params = [];
        if (data) {
            for (attr in data) {
                if (data.hasOwnProperty(attr)) {
                    params.push(attr+'='+data[attr]);
                }
            }
            if (params.length !== 0) {
                url += '?' + params.join('&');
            }
        }
        var req = this.newRequest('GET', url, cb);
        req.send();
        return req;
    };

    HMPrototype.post = function(url, data, cb) {
        var args = args4Method(arguments);
        var url = args[0], data = args[1], cb = args[2];
        data = JSON.stringify(data) || '';
        var req = this.newRequest('POST', url, cb);
        req.setRequestHeader("Content-Type", "application/json; charset=UTF-8");
        req.send(data);
        return req;
    };

    HMPrototype.put = function(url, data, cb) {
        var args = args4Method(arguments);
        var url = args[0], data = args[1], cb = args[2];
        data = JSON.stringify(data) || '';
        var req = this.newRequest('PUT', url, cb);
        req.setRequestHeader("Content-Type", "application/json; charset=UTF-8");
        req.send(data);
        return req;
    };

    HMPrototype.delete = function(url, data, cb) {
        var args = args4Method(arguments);
        var url = args[0], data = args[1], cb = args[2];
        var attr, params = [];
        if (data) {
            for (attr in data) {
                if (data.hasOwnProperty(attr)) {
                    params.push(attr+'='+data[attr]);
                }
            }
            if (params.length !== 0) {
                url += '?' + params.join('&');
            }
        }
        var req = this.newRequest('DELETE', url, cb);
        req.send();
        return req;
    };

    return pymaid;
});
