var stubs = function() {

    var channel = null;

    var bindChannel = function(ch) {
        if(channel) {
            cc.warn('service has already bound channel');
            return;
        }
        channel = ch;
    };

    var cbWrapper = function(cb) {
        var wrapper = function(packet) {
            var methods = packet.controller.service_method.split('.');
            var method = methods[methods.length-1];

            var err = null;
            if(packet.controller.is_failed) {
                err = Channel.ErrorMessage.decode(packet.content);
            }
            cb(err, packet.content);
        };
        return wrapper;
    };

    var rpc = function(method, req, cb) {
        channel.send(method, req, cbWrapper(cb));
    };

    var registerStub = function(StubClass) {
        var name = StubClass.$type.name;
        name = name[0].toLowerCase() + name.slice(1);
        this[name] = new StubClass(rpc);
    };

    return {
        bindChannel: bindChannel,
        registerStub: registerStub,
    }
}();