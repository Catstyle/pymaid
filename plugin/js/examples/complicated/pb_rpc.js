goog.require('proto.complicated.ComplicatedMessage');
(function(global) {
    (global['pbrpc'] = global['pbrpc'] || {})['Service'] = {
        name: 'complicated.Service',

        Test: {
            input_type: proto.complicated.ComplicatedMessage,
            output_type: proto.complicated.ComplicatedMessage,
        },

    };
})(this);
