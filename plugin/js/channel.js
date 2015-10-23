var Channel = cc.Class.extend({

    conn: null,
    isConnected: false,
    transmissionId: 0,
    transmissions: {},

    ctor: function() {
        var pymaid = dcodeIO.ProtoBuf.loadJsonFile("src/pymaid/pymaid.json");
        Channel.Controller = pymaid.build('pymaid.pb.Controller');
        Channel.Void = pymaid.build('pymaid.pb.Void');
        Channel.ErrorMessage = pymaid.build('pymaid.pb.ErrorMessage');
    },

    _packPacket: function(method, request) {
        var controller = new Channel.Controller({'service_method': method, 'packet_type': 1 /* request */, transmission_id: this.transmissionId++});
        var controllerLength = controller.calculate();
        var requestLength = request.calculate();

        // 5 is for '!BHH'
        var bb = new dcodeIO.ByteBuffer(5+controllerLength+requestLength);
        bb.writeUint8(1); // protobuf
        bb.writeUint16(controllerLength);
        bb.writeUint16(requestLength);
        bb.append(controller.toBuffer());
        bb.append(request.toBuffer());
        bb.flip();
        return {transmissionId: controller.transmission_id, buf: bb.toBuffer()};
    },

    _unpackPacket: function(binary) {
        var bb = dcodeIO.ByteBuffer.fromBinary(binary);
        var type = bb.readUint8();
        cc.assert(type == 1, 'should be pb parser');

        var controllerLength = bb.readUint16();
        var contentLength = bb.readUint16();

        // 5 is for '!BHH'
        var controllerBuf = bb.slice(5, 5+controllerLength);
        var controller = Channel.Controller.decode(controllerBuf);

        var contentBuf = null;
        if (contentLength) {
            contentBuf = bb.slice(5+controllerLength, 5+controllerLength+contentLength);
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

    connect: function(urlpath, cb) {
        if (this.conn && !this.conn.isClosed) {
            cc.warn('channel connection already connected');
            return;
        }
        this.conn = new Channel.ConnectionClass(urlpath, this);
        this.openCB = cb;
    },

    send: function(method, request, cb) {
        var packet = this._packPacket(method, request);
        this.conn.send(packet.buf);
        this.transmissions[packet.transmissionId] = cb
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
        var transmissionId = packet.controller.transmission_id;
        var cb = this.transmissions[transmissionId];
        delete this.transmissions[transmissionId];
        if (!cb) {
            cc.error('transmissionId: ' + transmissionId + 'has no cb');
            // what to do?
            return;
        }
        cb(packet);
    },

    onerror: function(evt) {
        cc.log('channel error', evt);
    },
});