var test = function() {
    goog.require('examples/complicated/pb_pb');
    var channel = new pymaid.Channel();
    channel.init_stubs(pbrpc);

    var wrapper = function() {
        var cb = function(err, resp) {
            if (!err) {
                console.log('receive resp: ' + JSON.stringify(resp));
            } else {
                console.log('receive error: ' + JSON.stringify(err));
            }
        };
        channel.stubs.service.Test({
            message: {message: 'haha哈'}, count: 5, uints: [1, 2, 3],
            messages: {1: {'message': '1'}, pbmap: true}
        }, cb);
    };
    channel.connect('ws', '127.0.0.1', 8888, {onopen: wrapper});
};

