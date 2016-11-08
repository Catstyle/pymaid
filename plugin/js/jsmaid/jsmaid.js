var jsmaid = {

    initHttpManager: function(rootUrl, clientClass, webimpl) {
        this.webimpl = webimpl;
        var httpManager = this.httpManager = new pymaid.HttpManager(clientClass);
        httpManager.setRootUrl(rootUrl);

        for (var impl in this.webimpl) {
            if (!this.webimpl.hasOwnProperty(impl)) {
                continue;
            }
            cc.log(impl + ' is binding httpManager');
            this.webimpl[impl].bindHttpManager(httpManager);
        }
    },

    initGameChannel: function(pbs, pbimpl, listenImpl) {
        this.pbs = pbs;
        this.pbimpl = pbimpl;
        this.listenImpl = listenImpl;

        this.gameChannel = new pymaid.Channel(pymaid.WSConnection, pymaid.PBParser);
        this.gameConn = null;

        // init stubs
        var stubs = this.stubs = new pymaid.StubManager();

        var getBuilder = function(pb_json, builders) {
            if (typeof pb_json !== 'object') {
                console.log('registerBuilder got argument is not json/object');
                return;
            }
            if (!pb_json.hasOwnProperty('syntax')) {
                for (var attr in pb_json) {
                    if (!pb_json.hasOwnProperty(attr)) {
                        continue;
                    }
                    getBuilder(pb_json[attr], builders);
                }
                return;
            }
            builders.push(dcodeIO.ProtoBuf.loadJson(pb_json));
        }

        var builders = [], builder;
        getBuilder(this.pbs, builders);
        for (var idx = 0, length = builders.length; idx < length; idx++) {
            stubs.registerBuilder(builders[idx]);
        }

        // init listener
        var listener = new pymaid.Listener();
        this.gameChannel.bindListener(listener);
        for (var impl in this.pbimpl) {
            if (!this.pbimpl.hasOwnProperty(impl)) {
                continue;
            }
            listener.registerImpl(this.pbimpl[impl]);
        }

        var listenImpl = this.listenImpl;
        builders = [];
        getBuilder(this.pbs, builders);
        for (var idx = 0, length = builders.length; idx < length; idx++) {
            listener.registerBuilder(builders[idx], function(name) {
                return listenImpl.indexOf(name) != -1;
            });
        }
    },

    isAlreadyConnected: function(address) {
        var gameConn = this.gameConn;
        if (gameConn && gameConn.address === address && !gameConn.is_closed) {
            return true;
        }
        return false;
    },

    connectGameServer: function(schema, host, port, callbacks) {
        var address = this._combineAddress(schema, host, port);
        if (this.isAlreadyConnected(address)) {
            console.log(
                'jsmaid: there is a conn already connected to address: ' + address
            );
            return this.gameConn;
        }
        if (this.gameConn) {
            this.disconnectGameServer('connecting to another server');
        }
        var conn = this.gameConn = this.gameChannel.connect(address, callbacks);
        this.stubs.bindConnection(conn);
        return conn;
    },

    disconnectGameServer: function(reason) {
        if (!this.gameConn || this.gameConn.is_closed) {
            return;
        }
        this.gameConn.close(reason);
    },

    _combineAddress: function(schema, host, port) {
        var address = host + ':' + port;
        if (schema == 'ws') {
            address = 'ws://' + address;
        }
        return address;
    },

};
