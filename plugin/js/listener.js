var Listener = cc.Class.extend({

    ctor: function() {
        this.classes = {};
        this.implementations = {};
    },

    _registerService: function(service) {
        var serviceName = service.fqn();
        var rpc = service.getChildren(dcodeIO.ProtoBuf.Reflect.Service.RPCMethod);
        for (var idx = 0; idx < rpc.length; ++idx) {
            var method = rpc[idx], serviceMethod = method.fqn();
            var impl = this.implementations[serviceName][method.name];
            cc.assert(impl && impl.constructor.name == 'Function',
                      'implementations has no method: ' + method.name);
            this.classes[serviceMethod] = this.classes[serviceMethod.slice(1)]= {
                req: method.resolvedRequestType.clazz,
                resp: method.resolvedResponseType.clazz
            };
        }
    },

    registerImpl: function(impl) {
        this.implementations[impl.name] = this.implementations['.'+impl.name] = impl;
    },

    registerBuilder: function(builder) {
        if (!builder.resolved) {
            builder.build();
        }
        var ns = builder.ns.children[0];
        var _services = ns.getChildren(dcodeIO.ProtoBuf.Reflect.Service);
        for (var idx = 0; idx < _services.length; ++idx) {
            this._registerService(_services[idx]);
        }
    },

    onmessage: function(channel, packet) {
        var serviceMethod = packet.controller.service_method;
        var dot = serviceMethod.lastIndexOf('.');
        var serviceName = serviceMethod.substr(0, dot);
        var methodName = serviceMethod.substr(dot+1);

        var impl = this.implementations[serviceName];
        if (!impl || !impl[methodName]) {
            this.onNoSuchImpl(serviceMethod);
            return;
        }
        var clazz = this.classes[serviceMethod];
        var controller = packet.controller;
        impl[methodName](controller, clazz.req.decode(packet.content), function(err, content) {
            if (clazz.resp.name == 'Void') {
                // failed silently when handle notification
                return;
            }
            controller.packet_type = Channel.Controller.PacketType.RESPONSE;
            if (err) {
                controller.is_failed = true;
                channel.sendResponse(controller, new Channel.ErrorMessage(err));
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
    },

    onNoSuchImpl: function(serviceMethod) {
        cc.warn('listener has no such impl: ' + serviceMethod);
    },
});
