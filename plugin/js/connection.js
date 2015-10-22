var WSConnection = cc.Class.extend({

    ws: null,

    ctor: function(urlpath, channel) {
        this.ws = new WebSocket(urlpath);
        this.ws.binaryType = 'arraybuffer';
        this.channel = channel;
        this.ws.onopen = this.onopen.bind(this);
        this.ws.onclose = this.onclose.bind(this);
        this.ws.onmessage = this.onmessage.bind(this);
        this.ws.onerror = this.onerror.bind(this);
    },

    send: function(buf) {
        this.ws.send(buf);
    },

    // avoid `this` pollution
    onopen: function(evt) {
        this.channel.onopen(evt)
    },

    onclose: function(evt) {
        this.channel.onclose(evt)
    },

    onmessage: function(evt) {
        this.channel.onmessage(evt)
    },

    onerror: function(evt) {
        this.channel.onerror(evt)
    },
});