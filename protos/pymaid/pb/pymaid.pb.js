var _root = dcodeIO.ProtoBuf.newBuilder({})['import']({
    "package": "pymaid.pb",
    "messages": [
        {
            "name": "Controller",
            "fields": [
                {
                    "rule": "optional",
                    "type": "string",
                    "name": "service_method",
                    "id": 1
                },
                {
                    "rule": "optional",
                    "type": "uint32",
                    "name": "packet_type",
                    "id": 2
                },
                {
                    "rule": "optional",
                    "type": "uint32",
                    "name": "transmission_id",
                    "id": 3
                },
                {
                    "rule": "optional",
                    "type": "bool",
                    "name": "is_canceled",
                    "id": 4
                },
                {
                    "rule": "optional",
                    "type": "bool",
                    "name": "is_failed",
                    "id": 5
                }
            ]
        },
        {
            "name": "Void",
            "fields": []
        },
        {
            "name": "ErrorMessage",
            "fields": [
                {
                    "rule": "required",
                    "type": "uint32",
                    "name": "error_code",
                    "id": 1
                },
                {
                    "rule": "required",
                    "type": "string",
                    "name": "error_message",
                    "id": 2
                }
            ]
        }
    ]
}).build();