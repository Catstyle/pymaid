var BaseStub = cc.Class.extend({

    channel: null,

    bindChannel: function(ch) {
        if(this.channel) {
            cc.warn('service has already bound channel');
            return;
        }
        this.channel = ch;
    },

    cbWrapper: function(cb) {
        var wrapper = function(packet) {
            var methods = packet.controller.service_method.split('.');
            var method = methods[methods.length-1];

            var status = 'successful';
            var content = packet.content;
            if(packet.controller.is_failed) {
                status = 'failed';
                content = this.channel.ErrorMessage.decode(content);
            } else {
                content = this.methods[method].responseClass.decode(content);
            }
            cb(status, content);
        };
        return wrapper.bind(this);
    },
});