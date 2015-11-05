var Stub = cc.Class.extend({

    channel: null,

    bindChannel: function(ch) {
        if (this.channel) {
            cc.warn('stubs has already bound channel');
            return;
        }
        this.channel = ch;
    },

    cbWrapper: function(cb) {
        var wrapper = function(packet) {
            var err = null;
            if (packet.controller.is_failed) {
                err = Channel.ErrorMessage.decode(packet.content);
            }
            cb(err, packet.content);
        };
        return wrapper;
    },

    rpc: function(method, req, cb) {
        this.channel.sendRequest(method, req, this.cbWrapper(cb));
    },

    registerStub: function(stub) {
        var name = stub.$type.name;
        name = name[0].toLowerCase() + name.slice(1);
        this[name] = new stub(this.rpc.bind(this));
    },
});
