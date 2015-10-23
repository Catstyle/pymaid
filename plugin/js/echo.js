var EchoServiceStub = BaseStub.extend({

    methods: {},

    ctor: function() {
        var builder = dcodeIO.ProtoBuf.loadProtoFile('src/pymaid/echo.proto');
        this.methods['echo'] = {
            requestClass: builder.build('echo.Message'),
            responseClass: builder.build('echo.Message')
        };
    },

    echo: function(args, cb) {
        var request = new this.methods['echo'].requestClass(args);
        this.channel.send('echo.EchoService.echo', request, this.cbWrapper(cb));
    },
})

var echoTest = function() {
    var channel = new Channel();
    channel.registerConnection(WSConnection);

    var stub = new EchoServiceStub();
    stub.bindChannel(channel);

    var echo = function(channel) {
        var cb = function(status, content) {
            cc.log('echo test status: ' + status);
            if (status == 'successful') {
                cc.log('echo receive msg: ' + content.message);
            } else /* status == 'failed' */ {
                cc.log('echo receive error: ' + content.error_code, content.error_message);
            }
        };
        stub.echo('haha', cb);
    };
    channel.connect('ws://192.168.2.235:8888', echo);
};