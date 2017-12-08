goog.require('proto.pymaid.pb');

(function(global, factory) {
    global['pymaid'] = factory();
})(this, function() {
    var pymaid = {};

    var pb = pymaid.pb = {};
    pb.Controller = proto.pymaid.pb.Controller;
    pb.Void = proto.pymaid.pb.Void;
    pb.ErrorMessage = proto.pymaid.pb.ErrorMessage;

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
        var ctrlBinary = controller.serializeBinary();
        var contentBinary = content.serializeBinary();
        var ctrlSize = ctrlBinary.byteLength;
        var contentSize = contentBinary.byteLength;

        var ab = new ArrayBuffer(this._headerSize + ctrlSize + contentSize);
        var dv = new DataView(ab, 0, 4);
        var ctrl = new Uint8Array(ab, 4, ctrlSize);
        var content = new Uint8Array(ab, 4 + ctrlSize, contentSize);
        dv.setUint16(0, ctrlSize);
        dv.setUint16(2, contentSize);
        ctrl.set(ctrlBinary);
        content.set(contentBinary);
        return ab;
    };

    PBParser.unpack = function(ab) {
        var dv = new DataView(ab, 0, 4);
        var ctrlSize = dv.getUint16(0);
        var contentSize = dv.getUint16(2);

        var ctrlLimit = this._headerSize + ctrlSize;
        return {
            controller: pb.Controller.deserializeBinary(ab.slice(this._headerSize, ctrlLimit)),
            content: ab.slice(ctrlLimit, ctrlLimit + contentSize)
        };
    };

    // haibin: comment out for now
    // JSONParser.pack = function(controller, content) {
    //     var ctrlJson = JSON.stringify(controller.toObject());
    //     var contentJson = JSON.stringify(content.toObject());
    //     var ctrlSize = ctrlJson.byteLength;
    //     var contentSize = contentJson.byteLength;

    //     var ab = new ArrayBuffer(this._headerSize + ctrlSize + contentSize);
    //     var header = new Uint16Array(ab, 0, 2);
    //     var ctrl = new Uint8Array(ab, 4, ctrlSize);
    //     var content = new Uint8Array(ab, 4 + ctrlSize, contentSize);
    //     header[0] = ctrlSize;
    //     header[1] = contentSize;
    //     bb.append(controller.encodeJSON());
    //     bb.append(content.encodeJSON());
    //     bb.flip();
    //     return bb.toBuffer();
    // };

    // JSONParser.unpack = function(ab) {
    //     var bb = dcodeIO.ByteBuffer.wrap(ab);
    //     var ctrlSize = bb.readUint16();
    //     var contentSize = bb.readUint16();

    //     var controllerBuf = bb.readString(ctrlSize);
    //     return {
    //         controller: pb.Controller.decode(JSON.parse(controllerBuf)),
    //         content: JSON.parse(bb.readString(contentSize))
    //     };
    // };


    /**
     * Channel, implement rpc pack/unpack
     *
    **/
    var Channel = function(parser) {
        this.conn = null;
        this.parser = parser || PBParser;
        this.is_closed = true;
        this.stubs = new pymaid.StubManager();
        this.listener = new pymaid.Listener();
    };

    var ChannelPrototype = Channel.prototype = Object.create(Channel.prototype);
    pymaid.Channel = Channel;

    ChannelPrototype._combineAddress = function(scheme, host, port) {
        var address = host + ':' + port;
        if (scheme === 'ws' || scheme === 'wss') {
            address = scheme + '://' + address;
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

    ChannelPrototype.connect = function(scheme, host, port, callbacks) {
        var address = this._combineAddress(scheme, host, port);
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

            onerror: callbacks.onerror || function() {},
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

    ChannelPrototype.init_stubs = function(pbrpc) {
        var stubs = this.stubs = new pymaid.StubManager();
        for (var attr in pbrpc) {
            if (pbrpc.hasOwnProperty(attr)) {
                stubs.register(attr, pbrpc[attr]);
            }
        }
    };

    ChannelPrototype.init_listener = function(pbimpl) {
        var listener = this.listener = new pymaid.Listener();
        for (var impl in pbimpl) {
            if (!pbimpl.hasOwnProperty(impl)) {
                continue;
            }
            listener.register(pbimpl[impl]);
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
            cb(pb.Controller.fromObject({isFailed: true}),
               pb.ErrorMessage.fromObject({
                   message: 'pymaid: rpc conn closed with [reason|' + reason + ']'
               }).serializeBinary()
            );
            delete this.transmissions[idx];
        }
    }

    WSConnectionPrototype.onmessage = function(evt) {
        var packet = this.parser.unpack(evt.data);
        var controller = packet.controller, content = packet.content;

        if (controller.getPacketType() == pb.Controller.PacketType.RESPONSE) {
            var tid = controller.getTransmissionId();
            var cb = this.transmissions[tid];
            if (!cb) {
                console.log(
                    'pymaid: [WSConnection|'+this.connid+'][transmission|'+tid+']' +
                    '[service_method|'+controller.getServiceMethod()+'] has no cb'
                );
                // what to do?
                return;
            }
            delete this.transmissions[tid];
            cb(controller, content);
        } else {
            this.channel && this.channel.listener.onmessage(controller, content, this);
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
        var serviceName = service.name;
        for (var rpc in service) {
            if (rpc === 'name' || !service.hasOwnProperty(rpc)) {
                continue;
            }
            (function(name, method) {
                var requestType = method.input_type;
                var responseType = method.output_type;

                var requireResponse = responseType !== pb.Void;
                var illegalResponse = {message: "Illegal response received in: " + name};

                this[name] = function(req, cb, conn) {
                    var conn = conn || this._manager.conn;
                    if (!cb || cb.constructor.name != 'Function') {
                        throw Error(
                            'pymaid: rpc cb is not function: ' + method.name
                        );
                    }
                    if (!conn || conn.is_closed) {
                        setTimeout(cb.bind(this, {message: 'pymaid: rpc conn is null/closed'}, null), 0);
                        return;
                    }

                    var controller = pb.Controller.fromObject({
                        serviceMethod: serviceName + '.' + name,
                        packetType: pb.Controller.PacketType.REQUEST,
                    });
                    if (requireResponse) {
                        var tid = conn.transmissionId;
                        controller.setTransmissionId(tid);
                        conn.transmissionId++;
                    }
                    if (!(req instanceof requestType)) {
                        req = requestType.fromObject(req);
                    }
                    console.log(
                        'pymaid: [Stub][controller|'+JSON.stringify(controller.toObject())+']'+
                        '[req|'+JSON.stringify(req.toObject())+']'
                    );
                    conn.send(conn.parser.pack(controller, req));

                    if (!requireResponse) {
                        setTimeout(cb.bind(this, null, null), 0);
                    } else {
                        conn.transmissions[tid] = function(controller, resp) {
                            var err = null, content;
                            if (!controller) {
                                err = content = illegalResponse;
                            } else if (controller.getIsFailed()) {
                                err = content = pb.ErrorMessage.deserializeBinary(resp);
                            } else {
                                try {
                                    resp = content = responseType.deserializeBinary(resp);
                                } catch (Error) {
                                }
                                if (!(resp instanceof responseType)) {
                                    err = content = illegalResponse;
                                }
                            }
                            console.log(
                                'pymaid: [WSConnection|'+conn.connid+'][address|'+conn.address+']'+
                                '[onmessage][controller|'+JSON.stringify(controller.toObject())+']'+
                                '[content|'+JSON.stringify(content.toObject())+']'
                            );
                            cb(err, resp);
                        };
                    }
                };
            }).bind(this)(rpc, service[rpc]);
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

    StubManagerPrototype.register = function(name, service) {
        console.log('pymaid: registering stub: ' + name);
        name = name[0].toLowerCase() + name.slice(1);
        this[name] = new Stub(this, service);
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
        this.implementations = {};
    };

    var ListenerPrototype = Object.create(Listener.prototype);
    Listener.prototype = ListenerPrototype;
    pymaid.Listener = Listener;

    ListenerPrototype._registerService = function(service) {
    };

    ListenerPrototype.register = function(impl) {
        var name = impl.name;
        console.log('pymaid: listener registering service: ' + name);
        this.implementations[name] = this.implementations['.'+name] = impl;
    };

    ListenerPrototype.onmessage = function(controller, content, conn) {
        var serviceMethod = controller.getServiceMethod();
        var dot = serviceMethod.lastIndexOf('.');
        var serviceName = serviceMethod.substr(0, dot);
        var methodName = serviceMethod.substr(dot+1);

        var impl = this.implementations[serviceName];
        if (!impl || !impl[methodName]) {
            this.onNoSuchImpl(serviceMethod);
            return;
        }
        var method = impl[methodName];
        var req = method.input_type.deserializeBinary(content), respType = method.output_type;
        console.log(
            'pymaid: [WSConnection|'+conn.connid+'][address|'+conn.address+']'+
            '[onmessage][controller|'+JSON.stringify(controller.toObject())+']' +
            '[content|'+JSON.stringify(req.toObject())+']'
        );
        impl[methodName](controller, req, function(err, content) {
            if (respType === pb.Void) {
                // when handle notification
                return;
            }
            controller.setPacketType(pb.Controller.PacketType.RESPONSE);
            if (err) {
                controller.setIsFailed(true);
                conn.send(conn.parser.pack(controller, pb.ErrorMessage.fromObject(err)));
            } else {
                if (content === null) {
                    throw Error('pymaid: impl: '+serviceMethod+' got null content');
                }
                if (!(content instanceof respType)) {
                    content = respType.fromObject(content);
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
    var HttpManager = function(rootUrl, webimpl, requestClass, timeout) {
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
        this.timeout = timeout || 30000;
    };

    var HMPrototype = HttpManager.prototype = Object.create(HttpManager.prototype);
    pymaid.HttpManager = HttpManager;

    var getParams = function(data) {
        var params = [], attr;
        if (data) {
            for (attr in data) {
                if (data.hasOwnProperty(attr)) {
                    params.push(attr+'='+data[attr]);
                }
            }
        }
        return params.join('&');
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
            this._cookies = cookies;
        }
    };

    HMPrototype.onNotAuthenticated = function() {
        console.log('pymaid HttpManager became not authenticated');
    };

    HMPrototype.newRequest = function(type, url, cb, timeout, async) {
        async = async || true;
        var self = this;

        var req = new this._requestClass();
        req.withCredentials = true;
        req.open(type.toUpperCase(), this._realUrl(url), async);
        req.setRequestHeader('Cookie', this._cookies);
        req.timeout = timeout || this.timeout;

        req.onload = function() {
            self.setCookies(req.getResponseHeader('Set-Cookie'));

            var status = req.status;
            var response = req.responseText;
            var err = null;

            if (status >= 200 && status <= 207) {
                try {
                    response = JSON.parse(response);
                } catch (e) {
                    if (e instanceof SyntaxError) {
                        err = {message: 'invalid json response', status: status};
                    } else {
                        throw e;
                    }
                }
            } else if (status == 301 || status == 302) {
                self.get(req.getResponseHeader('Location').trim(), {}, cb);
                return;
            } else if (status == 400) {
                try {
                    err = JSON.parse(response);
                } catch (e) {
                    if (!(e instanceof SyntaxError)) {
                        throw e;
                    }
                    err = {message: response, status: status};
                }
            } else if (status == 401) {
                self.onNotAuthenticated();
                return;
            } else {
                err = {message: response, status: status};
            }
            cb(err, response);
        };

        req.ontimeout = function() {
            cb({status: 444, message: 'http request timeout'});
        };

        req.onerror = function() {
            cb({message: 'http request onerror', status: req.status});
        };

        return req;
    };

    HMPrototype.get = function(url, data, cb, timeout) {
        var params = getParams(data);
        if (params) {
            url += '?' + params;
        }
        var req = this.newRequest('GET', url, cb, timeout);
        req.send();
        return req;
    };

    HMPrototype.post = function(url, data, cb, timeout) {
        var req = this.newRequest('POST', url, cb, timeout);
        req.setRequestHeader("Content-Type", "application/json; charset=UTF-8");
        req.send(data ? JSON.stringify(data) : '');
        return req;
    };

    HMPrototype.put = function(url, data, cb, timeout) {
        var req = this.newRequest('PUT', url, cb, timeout);
        req.setRequestHeader("Content-Type", "application/json; charset=UTF-8");
        req.send(data ? JSON.stringify(data) : '');
        return req;
    };

    HMPrototype.del = function(url, data, cb, timeout) {
        var params = getParams(data);
        if (params) {
            url += '?' + params;
        }
        var req = this.newRequest('DELETE', url, cb, timeout);
        req.send();
        return req;
    };

    return pymaid;
});
