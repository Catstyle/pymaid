var _root = dcodeIO.ProtoBuf.newBuilder({})['import']({
    "package": "pymaid",
    "messages": [
        {
            "name": "pb",
            "fields": [],
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
        },
        {
            "name": "apps",
            "fields": [],
            "messages": [
                {
                    "name": "monitor",
                    "fields": [],
                    "options": {
                        "py_generic_services": true
                    },
                    "messages": [
                        {
                            "name": "HeartbeatInfo",
                            "fields": [
                                {
                                    "rule": "required",
                                    "type": "bool",
                                    "name": "need_heartbeat",
                                    "id": 1
                                },
                                {
                                    "rule": "optional",
                                    "type": "float",
                                    "name": "heartbeat_interval",
                                    "id": 2
                                }
                            ]
                        }
                    ],
                    "services": [
                        {
                            "name": "MonitorService",
                            "options": {},
                            "rpc": {
                                "notify_heartbeat": {
                                    "request": "pb.Void",
                                    "response": "pb.Void",
                                    "options": {}
                                },
                                "get_heartbeat_info": {
                                    "request": "pb.Void",
                                    "response": "HeartbeatInfo",
                                    "options": {}
                                }
                            }
                        }
                    ]
                }
            ]
        }
    ]
}).build();