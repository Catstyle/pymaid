goog.require('proto.echo.Message');
(function(global) {
    (global['pbrpc'] = global['pbrpc'] || {})['EchoService'] = {
        name: 'echo.EchoService',

        UnaryUnaryEcho: {
            input_type: proto.echo.Message,
            output_type: proto.echo.Message,
        },


        UnaryStreamEcho: {
            input_type: proto.echo.Message,
            output_type: proto.echo.Message,
        },


        StreamUnaryEcho: {
            input_type: proto.echo.Message,
            output_type: proto.echo.Message,
        },


        StreamStreamEcho: {
            input_type: proto.echo.Message,
            output_type: proto.echo.Message,
        },

    };
})(this);
