var jsmaid = {

    initHttpManager: function(rootUrl, clientClass, webimpl) {
        this.webimpl = webimpl;
        var httpManager = this.httpManager = new pymaid.HttpManager(clientClass);
        cc.log("rootUrl: ' rootUrl);
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
        for (var pb in this.pbs) {
            if (!this.pbs.hasOwnProperty(pb)) {
                continue;
            }
            cc.log('pbs: ' + pb);
            var builder = dcodeIO.ProtoBuf.loadJson(this.pbs[pb]);
            stubs.registerBuilder(builder);
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
        for (var pb in this.pbs) {
            if (!this.pbs.hasOwnProperty(pb)) {
                continue;
            }
            var builder = dcodeIO.ProtoBuf.loadJson(this.pbs[pb]);
            listener.registerBuilder(builder, function(name) {
                return listenImpl.indexOf(name) != -1;
            });
        }
    },

    isAlreadyConnected: function(schema, host, port) {
        var address = host + ':' + port;
        if (schema == 'ws') {
            address = 'ws://' + address;
        }
        var gameConn = this.gameConn;
        if (gameConn && gameConn.address === address && !gameConn.is_closed) {
            return true;
        }
        return false;
    },

    connectGameServer: function(schema, host, port, callbacks) {
        if (this.isAlreadyConnected(schema, host, port)) {
            console.log('jsmaid: there is a conn already connected to address: '+address);
            return this.gameConn;
        }
        if (this.gameConn) {
            this.disconnectGameServer('connecting to another server');
        }
        var address = host + ':' + port;
        if (schema == 'ws') {
            address = 'ws://' + address;
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

};
