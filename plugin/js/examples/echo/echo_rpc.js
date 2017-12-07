goog.require('proto.echo.Message');
(function(global) {
    (global['pbrpc'] = global['pbrpc'] || {})['EchoService'] = {
        name: 'echo.EchoService',

        Echo: {
            input_type: proto.echo.Message,
            output_type: proto.echo.Message,
        },

    };
})(this);
