var echoTest = function() {
    var channel = new Channel();
    channel.registerConnection(WSConnection);

    var builder = dcodeIO.ProtoBuf.loadProtoFile('src/pymaid/echo.proto');
    stubs.registerStub(builder.build('echo.EchoService'));

    var echo = function(channel) {
        var cb = function(err, res) {
            cc.log('echo test response: ' + err + ':' + res);
            if (!err) {
                cc.log('echo receive msg: ' + res.message);
            } else {
                cc.log('echo receive error: ' + err.error_code, err.error_message);
            }
        };
        stubs.bindChannel(channel);
        stubs.echoService.echo({message: 'haha'}, cb);
    };
    channel.connect('ws://192.168.2.235:8888', echo);
};