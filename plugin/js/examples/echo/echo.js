var echoTest = function() {
    var channel = new pymaid.Channel(pymaid.WSConnection);

    var pbJson = {
        "package": "echo",
        "options": {
            "py_generic_services": true
        },
        "messages": [
            {
                "name": "Message",
                "fields": [
                    {
                        "rule": "optional",
                        "type": "string",
                        "name": "message",
                        "id": 1
                    }
                ]
            }
        ],
        "services": [
            {
                "name": "EchoService",
                "options": {},
                "rpc": {
                    "echo": {
                        "request": "Message",
                        "response": "Message",
                        "options": {}
                    }
                }
            }
        ]
    };
    var builder = dcodeIO.ProtoBuf.loadJson(pbJson);
    var root = builder.build(); // resolved all protos

    var stubs = new pymaid.Stub(channel);
    stubs.registerStub(root.echo.EchoService);

    var echo = function(channel) {
        var cb = function(err, resp) {
            cc.log('err: ' + err + ', resp: ' + resp);
            if (!err) {
                cc.log('receive resp: ' + resp.message);
            } else {
                cc.log('receive error: ' + err.error_code, err.error_message);
            }
        };
        stubs.echoService.echo({message: 'haha'}, cb);
    };
    channel.connect('ws://192.168.2.235:8888', echo);
};
