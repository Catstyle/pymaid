var EchoServiceImpl = {
    echo: function(controller, request, cb) {
        cc.log('echo.EchoService received msg: ' + request.message);
        cb(null, request);
    }
};
EchoServiceImpl.name = 'echo.EchoService';

var echoTest = function() {
    var channel = new Channel();
    channel.registerConnection(WSConnection);

    var builder = dcodeIO.ProtoBuf.loadJsonFile('src/pymaid/echo.json');
    var root = builder.build(); // resolved all protos

    var stubs = new Stub();
    stubs.registerStub(root.echo.EchoService);
    stubs.bindChannel(channel);

    var listener = new Listener();
    listener.registerImpl(EchoServiceImpl);
    listener.registerBuilder(builder);

    channel.bindListener(listener);

    var echo = function(channel) {
        var cb = function(err, res) {
            cc.log('echo test response: ' + err + ':' + res);
            if (!err) {
                cc.log('echo receive msg: ' + res.message);
            } else {
                cc.log('echo receive error: ' + err.error_code, err.error_message);
            }
        };
        stubs.echoService.echo({message: 'haha'}, cb);
    };
    channel.connect('ws://192.168.2.235:8888', echo);
};
