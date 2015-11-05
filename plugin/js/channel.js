var Channel = cc.Class.extend({

    conn: null,
    listener: null,

    isConnected: false,
    transmissionId: 0,
    transmissions: {},

    _headerSize: 5,

    ctor: function() {
        var pymaid = dcodeIO.ProtoBuf.loadJsonFile("./pymaid.json").build('pymaid');
        Channel.Controller = pymaid.pb.Controller;
        Channel.Void = pymaid.pb.Void;
        Channel.ErrorMessage = pymaid.pb.ErrorMessage;
    },

    _packPacket: function(controller, content) {
        var ctrlSize = controller.calculate();
        var contentSize = content.calculate();

        // 5 is for '!BHH'
        var bb = new dcodeIO.ByteBuffer(this._headerSize + ctrlSize + contentSize);
        bb.writeUint8(1); // protobuf
        bb.writeUint16(ctrlSize);
        bb.writeUint16(contentSize);
        bb.append(controller.toBuffer());
        bb.append(content.toBuffer());
        bb.flip();
        return bb.toBuffer();
    },

    _unpackPacket: function(ab) {
        var bb = dcodeIO.ByteBuffer.wrap(ab);
        var type = bb.readUint8();
        cc.assert(type == 1, 'should be pb parser');

        var ctrlSize = bb.readUint16();
        var contentSize = bb.readUint16();

        // 5 is for '!BHH'
        var headerSize = this._headerSize;
        var ctrlLimit = headerSize + ctrlSize;
        var controllerBuf = bb.slice(headerSize, ctrlLimit);
        var controller = Channel.Controller.decode(controllerBuf);

        var contentBuf = null;
        if (contentSize) {
            contentBuf = bb.slice(ctrlLimit, ctrlLimit + contentSize);
        }

        return {controller: controller, content: contentBuf};
    },

    registerConnection: function(connectionClass) {
        if (Channel.ConnectionClass) {
            cc.warn('ConnectionClass already registered: ' + Channel.ConnectionClass);
            return;
        }
        Channel.ConnectionClass = connectionClass;
    },

    bindListener: function(listener) {
        if (this.listener) {
            cc.warn('already bound listener: ' + this.listener);
            return;
        }
        this.listener = listener;
    },

    connect: function(urlpath, cb) {
        if (this.conn && !this.conn.isClosed) {
            cc.warn('channel connection already connected');
            return;
        }
        this.conn = new Channel.ConnectionClass(urlpath, this);
        this.openCB = cb;
    },

    sendRequest: function(method, request, cb) {
        var controller = new Channel.Controller({
            service_method: method,
            packet_type: Channel.Controller.PacketType.REQUEST,
            transmission_id: this.transmissionId++
        });
        this.conn.send(this._packPacket(controller, request));
        this.transmissions[method] = cb
    },

    sendResponse: function(controller, response) {
        this.conn.send(this._packPacket(controller, response));
    },

    close: function() {
        this.conn.close();
    },

    onopen: function(evt) {
        cc.log('channel opened');
        cc.isConnected = true;
        if(this.openCB) {
            this.openCB(this, evt);
        }
    },

    onclose: function(evt) {
        cc.log('channel closed');
    },

    onmessage: function(evt) {
        var packet = this._unpackPacket(evt.data);
        if (packet.controller.packet_type == Channel.Controller.PacketType.RESPONSE) {
            this.onresponse(packet);
        } else {
            this.listener.onmessage(this, packet);
        }
    },

    onresponse: function(packet) {
        var method = packet.controller.service_method;
        var cb = this.transmissions[method];
        if (!cb) {
            cc.error('method: ' + method + 'has no cb');
            // what to do?
            return;
        }
        cb(packet);
    },

    onerror: function(evt) {
        cc.log('channel error', evt);
    },
});
