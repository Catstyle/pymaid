var echoTest = function() {
    goog.require('examples/echo/echo_pb');
    var channel = new pymaid.Channel(pbrpc, {});

    var echo = function() {
        var cb = function(err, resp) {
            if (!err) {
                console.log('receive resp: ' + resp.getMessage());
            } else {
                console.log('receive error: ' + JSON.stringify(err.toObject()));
            }
        };
        channel.stubs.echoService.Echo({message: 'haha哈'}, cb);
    };
    channel.connect('ws', '127.0.0.1', 8888, {onopen: echo});
};

