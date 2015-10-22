var echoTest = function() {
    var channel = new Channel();
    channel.registerConnection(WSConnection);
    channel.connect('ws://192.168.2.235:8888', echo);
}

var echo = function(channel) {
    var builder = dcodeIO.ProtoBuf.loadProtoFile('src/pymaid/echo.proto');
    var Message = builder.build('echo.Message');
    var msg = new Message({message: 'haha'});

    var cb = function(content) {
        var msg = Message.decode(content);
        cc.log('echo receive msg: ' + msg.message);
    }
    channel.send('echo.EchoService.echo', msg, cb);
}