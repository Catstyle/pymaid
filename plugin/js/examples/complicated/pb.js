/**
 * @fileoverview
 * @enhanceable
 * @suppress {messageConventions} JS Compiler reports an error if a variable or
 *     field starts with 'MSG_' and isn't a translatable message.
 * @public
 */
// GENERATED CODE -- DO NOT EDIT!

goog.provide('proto.complicated.ComplicatedMessage');
goog.provide('proto.complicated.Message');
goog.require('jspb.BinaryReader');
goog.require('jspb.BinaryWriter');
goog.require('jspb.Map');
goog.require('jspb.Message');


/**
 * Generated by JsPbCodeGenerator.
 * @param {Array=} opt_data Optional initial data array, typically from a
 * server response, or constructed directly in Javascript. The array is used
 * in place and becomes part of the constructed object. It is not cloned.
 * If no data is provided, the constructed object will be empty, but still
 * valid.
 * @extends {jspb.Message}
 * @constructor
 */
proto.complicated.Message = function(opt_data) {
  jspb.Message.initialize(this, opt_data, 0, -1, null, null);
};
goog.inherits(proto.complicated.Message, jspb.Message);
if (goog.DEBUG && !COMPILED) {
  proto.complicated.Message.displayName = 'proto.complicated.Message';
}


if (jspb.Message.GENERATE_TO_OBJECT) {
/**
 * Creates an object representation of this proto suitable for use in Soy templates.
 * Field names that are reserved in JavaScript and will be renamed to pb_name.
 * To access a reserved field use, foo.pb_<name>, eg, foo.pb_default.
 * For the list of reserved names please see:
 *     com.google.apps.jspb.JsClassTemplate.JS_RESERVED_WORDS.
 * @param {boolean=} opt_includeInstance Whether to include the JSPB instance
 *     for transitional soy proto support: http://goto/soy-param-migration
 * @return {!Object}
 */
proto.complicated.Message.prototype.toObject = function(opt_includeInstance) {
  return proto.complicated.Message.toObject(opt_includeInstance, this);
};


/**
 * Static version of the {@see toObject} method.
 * @param {boolean|undefined} includeInstance Whether to include the JSPB
 *     instance for transitional soy proto support:
 *     http://goto/soy-param-migration
 * @param {!proto.complicated.Message} msg The msg instance to transform.
 * @return {!Object}
 * @suppress {unusedLocalVariables} f is only used for nested messages
 */
proto.complicated.Message.toObject = function(includeInstance, msg) {
  var f, obj = {
    message: jspb.Message.getFieldWithDefault(msg, 1, "")
  };

  if (includeInstance) {
    obj.$jspbMessageInstance = msg;
  }
  return obj;
};
}


if (jspb.Message.GENERATE_FROM_OBJECT) {
/**
 * Loads data from an object into a new instance of this proto.
 * @param {!Object} obj The object representation of this proto to
 *     load the data from.
 * @return {!proto.complicated.Message}
 */
proto.complicated.Message.fromObject = function(obj) {
  var f, msg = new proto.complicated.Message();
  goog.isDef(obj.message) && jspb.Message.setField(msg, 1, obj.message);
  return msg;
};
}
/**
 * Deserializes binary data (in protobuf wire format).
 * @param {jspb.ByteSource} bytes The bytes to deserialize.
 * @return {!proto.complicated.Message}
 */
proto.complicated.Message.deserializeBinary = function(bytes) {
  var reader = new jspb.BinaryReader(bytes);
  var msg = new proto.complicated.Message;
  return proto.complicated.Message.deserializeBinaryFromReader(msg, reader);
};


/**
 * Deserializes binary data (in protobuf wire format) from the
 * given reader into the given message object.
 * @param {!proto.complicated.Message} msg The message object to deserialize into.
 * @param {!jspb.BinaryReader} reader The BinaryReader to use.
 * @return {!proto.complicated.Message}
 */
proto.complicated.Message.deserializeBinaryFromReader = function(msg, reader) {
  while (reader.nextField()) {
    if (reader.isEndGroup()) {
      break;
    }
    var field = reader.getFieldNumber();
    switch (field) {
    case 1:
      var value = /** @type {string} */ (reader.readString());
      msg.setMessage(value);
      break;
    default:
      reader.skipField();
      break;
    }
  }
  return msg;
};


/**
 * Serializes the message to binary data (in protobuf wire format).
 * @return {!Uint8Array}
 */
proto.complicated.Message.prototype.serializeBinary = function() {
  var writer = new jspb.BinaryWriter();
  proto.complicated.Message.serializeBinaryToWriter(this, writer);
  return writer.getResultBuffer();
};


/**
 * Serializes the given message to binary data (in protobuf wire
 * format), writing to the given BinaryWriter.
 * @param {!proto.complicated.Message} message
 * @param {!jspb.BinaryWriter} writer
 * @suppress {unusedLocalVariables} f is only used for nested messages
 */
proto.complicated.Message.serializeBinaryToWriter = function(message, writer) {
  var f = undefined;
  f = message.getMessage();
  if (f.length > 0) {
    writer.writeString(
      1,
      f
    );
  }
};


/**
 * optional string message = 1;
 * @return {string}
 */
proto.complicated.Message.prototype.getMessage = function() {
  return /** @type {string} */ (jspb.Message.getFieldWithDefault(this, 1, ""));
};


/** @param {string} value */
proto.complicated.Message.prototype.setMessage = function(value) {
  jspb.Message.setProto3StringField(this, 1, value);
};



/**
 * Generated by JsPbCodeGenerator.
 * @param {Array=} opt_data Optional initial data array, typically from a
 * server response, or constructed directly in Javascript. The array is used
 * in place and becomes part of the constructed object. It is not cloned.
 * If no data is provided, the constructed object will be empty, but still
 * valid.
 * @extends {jspb.Message}
 * @constructor
 */
proto.complicated.ComplicatedMessage = function(opt_data) {
  jspb.Message.initialize(this, opt_data, 0, -1, proto.complicated.ComplicatedMessage.repeatedFields_, null);
};
goog.inherits(proto.complicated.ComplicatedMessage, jspb.Message);
if (goog.DEBUG && !COMPILED) {
  proto.complicated.ComplicatedMessage.displayName = 'proto.complicated.ComplicatedMessage';
}
/**
 * List of repeated fields within this message type.
 * @private {!Array<number>}
 * @const
 */
proto.complicated.ComplicatedMessage.repeatedFields_ = [2];



if (jspb.Message.GENERATE_TO_OBJECT) {
/**
 * Creates an object representation of this proto suitable for use in Soy templates.
 * Field names that are reserved in JavaScript and will be renamed to pb_name.
 * To access a reserved field use, foo.pb_<name>, eg, foo.pb_default.
 * For the list of reserved names please see:
 *     com.google.apps.jspb.JsClassTemplate.JS_RESERVED_WORDS.
 * @param {boolean=} opt_includeInstance Whether to include the JSPB instance
 *     for transitional soy proto support: http://goto/soy-param-migration
 * @return {!Object}
 */
proto.complicated.ComplicatedMessage.prototype.toObject = function(opt_includeInstance) {
  return proto.complicated.ComplicatedMessage.toObject(opt_includeInstance, this);
};


/**
 * Static version of the {@see toObject} method.
 * @param {boolean|undefined} includeInstance Whether to include the JSPB
 *     instance for transitional soy proto support:
 *     http://goto/soy-param-migration
 * @param {!proto.complicated.ComplicatedMessage} msg The msg instance to transform.
 * @return {!Object}
 * @suppress {unusedLocalVariables} f is only used for nested messages
 */
proto.complicated.ComplicatedMessage.toObject = function(includeInstance, msg) {
  var f, obj = {
    message: (f = msg.getMessage()) && proto.complicated.Message.toObject(includeInstance, f),
    uintsList: jspb.Message.getRepeatedField(msg, 2),
    messagesMap: (f = msg.getMessagesMap()) ? f.toObject(includeInstance, proto.complicated.Message.toObject) : [],
    count: jspb.Message.getFieldWithDefault(msg, 4, 0)
  };

  if (includeInstance) {
    obj.$jspbMessageInstance = msg;
  }
  return obj;
};
}


if (jspb.Message.GENERATE_FROM_OBJECT) {
/**
 * Loads data from an object into a new instance of this proto.
 * @param {!Object} obj The object representation of this proto to
 *     load the data from.
 * @return {!proto.complicated.ComplicatedMessage}
 */
proto.complicated.ComplicatedMessage.fromObject = function(obj) {
  var f, msg = new proto.complicated.ComplicatedMessage();
  goog.isDef(obj.message) && jspb.Message.setWrapperField(
      msg, 1, proto.complicated.Message.fromObject(obj.message));
  goog.isDef(obj.uintsList) && jspb.Message.setField(msg, 2, obj.uintsList);
  goog.isDef(obj.messagesMap) && jspb.Message.setWrapperField(
      msg, 3, jspb.Map.fromObject(obj.messagesMap, proto.complicated.Message, proto.complicated.Message.fromObject));
  goog.isDef(obj.count) && jspb.Message.setField(msg, 4, obj.count);
  return msg;
};
}
/**
 * Deserializes binary data (in protobuf wire format).
 * @param {jspb.ByteSource} bytes The bytes to deserialize.
 * @return {!proto.complicated.ComplicatedMessage}
 */
proto.complicated.ComplicatedMessage.deserializeBinary = function(bytes) {
  var reader = new jspb.BinaryReader(bytes);
  var msg = new proto.complicated.ComplicatedMessage;
  return proto.complicated.ComplicatedMessage.deserializeBinaryFromReader(msg, reader);
};


/**
 * Deserializes binary data (in protobuf wire format) from the
 * given reader into the given message object.
 * @param {!proto.complicated.ComplicatedMessage} msg The message object to deserialize into.
 * @param {!jspb.BinaryReader} reader The BinaryReader to use.
 * @return {!proto.complicated.ComplicatedMessage}
 */
proto.complicated.ComplicatedMessage.deserializeBinaryFromReader = function(msg, reader) {
  while (reader.nextField()) {
    if (reader.isEndGroup()) {
      break;
    }
    var field = reader.getFieldNumber();
    switch (field) {
    case 1:
      var value = new proto.complicated.Message;
      reader.readMessage(value,proto.complicated.Message.deserializeBinaryFromReader);
      msg.setMessage(value);
      break;
    case 2:
      var value = /** @type {!Array<number>} */ (reader.readPackedUint32());
      msg.setUintsList(value);
      break;
    case 3:
      var value = msg.getMessagesMap();
      reader.readMessage(value, function(message, reader) {
        jspb.Map.deserializeBinary(message, reader, jspb.BinaryReader.prototype.readUint32, jspb.BinaryReader.prototype.readMessage, proto.complicated.Message.deserializeBinaryFromReader);
         });
      break;
    case 4:
      var value = /** @type {number} */ (reader.readUint32());
      msg.setCount(value);
      break;
    default:
      reader.skipField();
      break;
    }
  }
  return msg;
};


/**
 * Serializes the message to binary data (in protobuf wire format).
 * @return {!Uint8Array}
 */
proto.complicated.ComplicatedMessage.prototype.serializeBinary = function() {
  var writer = new jspb.BinaryWriter();
  proto.complicated.ComplicatedMessage.serializeBinaryToWriter(this, writer);
  return writer.getResultBuffer();
};


/**
 * Serializes the given message to binary data (in protobuf wire
 * format), writing to the given BinaryWriter.
 * @param {!proto.complicated.ComplicatedMessage} message
 * @param {!jspb.BinaryWriter} writer
 * @suppress {unusedLocalVariables} f is only used for nested messages
 */
proto.complicated.ComplicatedMessage.serializeBinaryToWriter = function(message, writer) {
  var f = undefined;
  f = message.getMessage();
  if (f != null) {
    writer.writeMessage(
      1,
      f,
      proto.complicated.Message.serializeBinaryToWriter
    );
  }
  f = message.getUintsList();
  if (f.length > 0) {
    writer.writePackedUint32(
      2,
      f
    );
  }
  f = message.getMessagesMap(true);
  if (f && f.getLength() > 0) {
    f.serializeBinary(3, writer, jspb.BinaryWriter.prototype.writeUint32, jspb.BinaryWriter.prototype.writeMessage, proto.complicated.Message.serializeBinaryToWriter);
  }
  f = message.getCount();
  if (f !== 0) {
    writer.writeUint32(
      4,
      f
    );
  }
};


/**
 * optional Message message = 1;
 * @return {?proto.complicated.Message}
 */
proto.complicated.ComplicatedMessage.prototype.getMessage = function() {
  return /** @type{?proto.complicated.Message} */ (
    jspb.Message.getWrapperField(this, proto.complicated.Message, 1));
};


/** @param {?proto.complicated.Message|undefined} value */
proto.complicated.ComplicatedMessage.prototype.setMessage = function(value) {
  jspb.Message.setWrapperField(this, 1, value);
};


proto.complicated.ComplicatedMessage.prototype.clearMessage = function() {
  this.setMessage(undefined);
};


/**
 * Returns whether this field is set.
 * @return {!boolean}
 */
proto.complicated.ComplicatedMessage.prototype.hasMessage = function() {
  return jspb.Message.getField(this, 1) != null;
};


/**
 * repeated uint32 uints = 2;
 * @return {!Array<number>}
 */
proto.complicated.ComplicatedMessage.prototype.getUintsList = function() {
  return /** @type {!Array<number>} */ (jspb.Message.getRepeatedField(this, 2));
};


/** @param {!Array<number>} value */
proto.complicated.ComplicatedMessage.prototype.setUintsList = function(value) {
  jspb.Message.setField(this, 2, value || []);
};


/**
 * @param {!number} value
 * @param {number=} opt_index
 */
proto.complicated.ComplicatedMessage.prototype.addUints = function(value, opt_index) {
  jspb.Message.addToRepeatedField(this, 2, value, opt_index);
};


proto.complicated.ComplicatedMessage.prototype.clearUintsList = function() {
  this.setUintsList([]);
};


/**
 * map<uint32, Message> messages = 3;
 * @param {boolean=} opt_noLazyCreate Do not create the map if
 * empty, instead returning `undefined`
 * @return {!jspb.Map<number,!proto.complicated.Message>}
 */
proto.complicated.ComplicatedMessage.prototype.getMessagesMap = function(opt_noLazyCreate) {
  return /** @type {!jspb.Map<number,!proto.complicated.Message>} */ (
      jspb.Message.getMapField(this, 3, opt_noLazyCreate,
      proto.complicated.Message));
};


proto.complicated.ComplicatedMessage.prototype.clearMessagesMap = function() {
  this.getMessagesMap().clear();
};


/**
 * optional uint32 count = 4;
 * @return {number}
 */
proto.complicated.ComplicatedMessage.prototype.getCount = function() {
  return /** @type {number} */ (jspb.Message.getFieldWithDefault(this, 4, 0));
};


/** @param {number} value */
proto.complicated.ComplicatedMessage.prototype.setCount = function(value) {
  jspb.Message.setProto3IntField(this, 4, value);
};

