from TProtocol import *
from struct import pack, unpack

__all__ = ['TCompactProtocol', 'TCompactProtocolFactory']

CLEAR = 0
WRITE = 1
BOOL_WRITE = 2
VALUE_WRITE = 3
CONTAINER_WRITE = 7
READ = 4
VALUE_READ = 6
CONTAINER_READ = 8
TRUE_READ = 9
FALSE_READ = 10

def make_helper(v_from, v_to, container):
  def helper(func):
    def nested(self, *args, **kwargs):
      assert self.state == v_from or self.state == container
      try:
        return func(self, *args, **kwargs)
      finally:
        if self.state == v_from:
          self.state = v_to
    return nested
  return helper
writer = make_helper(VALUE_WRITE, WRITE, CONTAINER_WRITE)
reader = make_helper(VALUE_READ, READ, CONTAINER_READ)

def makeZigZag(n, bits):
  import sys
  sys.stderr.write('%s, %s\n' % (n, bits))
  return (n << 1) ^ (n >> (bits - 1))

def fromZigZag(n, bits):
  return (n >> 1) ^ -(n & 1)

class CompactType:
  TRUE = 1
  FALSE = 2
  BYTE = 0x03
  I16 = 0x04
  I32 = 0x05
  I64 = 0x06
  DOUBLE = 0x07
  BINARY = 0x08
  LIST = 0x09
  SET = 0x0A
  MAP = 0x0B
  STRUCT = 0x0C

CTYPES = {TType.BOOL: CompactType.TRUE, # used for collection
          TType.BYTE: CompactType.BYTE,
          TType.I16: CompactType.I16,
          TType.I32: CompactType.I32,
          TType.I64: CompactType.I64,
          TType.DOUBLE: CompactType.DOUBLE,
          TType.STRING: CompactType.BINARY,
          TType.STRUCT: CompactType.STRUCT,
          TType.LIST: CompactType.LIST,
          TType.SET: CompactType.SET,
          TType.MAP: CompactType.MAP,
          }

TTYPES = {}
for k, v in CTYPES.items():
  TTYPES[v] = k
TTYPES[CompactType.FALSE] = TType.BOOL
del k
del v

class TCompactProtocol(TProtocolBase):
  "Compact implementation of the Thrift protocol driver."

  PROTOCOL_ID = 0x82
  VERSION = 1
  VERSION_MASK = 0x1f
  TYPE_MASK = 0xe0
  SHIFT_AMOUNT = 5

  state = CLEAR
  __last = 0
  __seqid = 0
  def __init__(self, trans):
    TProtocolBase.__init__(self, trans)
    self.__structs = []

  def writeMessageBegin(self, name, type, seqid):
    assert self.state == CLEAR
    self.__writeByte(self.PROTOCOL_ID)
    self.__writeByte(self.VERSION | (type << self.SHIFT_AMOUNT))
    self.__writeVarint(seqid)
    self.__writeString(name)
    self.state = WRITE

  def writeMessageEnd(self):
    assert self.state == WRITE
    self.state = CLEAR

  def writeStructBegin(self, name):
    assert self.state == CLEAR or self.state == WRITE or \
          self.state == CONTAINER_WRITE
    self.__structs.append((self.state, self.__last))
    self.state = WRITE
    self.__last = 0

  def writeStructEnd(self):
    assert self.state == WRITE
    self.state, self.__last = self.__structs.pop()

  def __writeFieldHeader(self, type, seqid):
    try:
      if self.__last and seqid > self.__last:
        delta = seqid - self.__last
        if delta < 16:
          self.writeByte(delta << 4 | type)
          return
      self.__writeByte(type)
    finally:
      self.__writeI16(seqid)
      self.__last = seqid

  def writeFieldBegin(self, name, type, seqid):
    assert self.state == WRITE
    if type == TType.BOOL:
      self.state = BOOL_WRITE
      self.__seqid = seqid
    else:
      self.state = VALUE_WRITE
      self.__writeFieldHeader(CTYPES[type], seqid)

  def __writeByte(self, byte):
    self.trans.write(pack('!b', byte))

  def __writeI16(self, i16):
    self.__writeVarint(makeZigZag(i16, 16))

  def __writeVarint(self, n):
    out = []
    while True:
      if n & 0x80 == 0:
        out.append(n)
        break
      else:
        out.append(n & 0xff)
        n = n >> 7
    print out
    self.trans.write(''.join(map(chr, out)))

  def __writeSize(self, i32):
    if i32 > 0x7fff:
      raise TException("thrift can't handle strings longer 0x7FFF")
    self.__writeVarint(i32)

  def readFieldBegin(self):
    assert self.state == READ
    type = self.__readByte()
    if type & 0x0f == TType.STOP:
      return
    delta = type >> 4
    if delta == 0:
      id = self.__readI16
    else:
      id = self.__last + delta
      self.__last = id
    if type == CompactType.TRUE:
      self.state = BOOL_READ
    elif type == CompactType.FALSE:
      self.state = BOOL_READ
    else:
      self.state = VALUE_READ
    return None, self.__getTType(type), id

  def writeCollectionBegin(self, etype, size):
    assert self.state == VALUE_WRITE
    if size <= 14:
      self.__writeByte(size << 4 | CTYPES[etype])
    else:
      self.__writeByte(0xf0 | CTYPES[etype])
      self.__writeSize(size)
    self.state = CONTAINER_WRITE
  writeSetBegin = writeCollectionBegin
  writeListBegin = writeCollectionBegin

  def writeMapBegin(self, ktype, vtype, size):
    assert self.state == VALUE_WRITE
    if size == 0:
      self.__writeByte(0)
    else:
      self.__writeSize(size)
      self.__writeByte(CTYPES[ktype] << 4 | CTYPES[vtype])
    self.state = CONTAINER_WRITE

  def writeBool(self, bool):
    if self.state == BOOL_WRITE:
      self.__writeFieldHeader(types[bool], self.__seqid)
    elif self.state == VALUE_WRITE:
      self.__writeByte(int(bool))
    else:
      raise AssertetionError, "Invalid state in compact protocol"
    self.state = WRITE

  writeByte = writer(__writeByte)
  writeI16 = writer(__writeI16)

  @writer
  def writeI32(self, i32):
    self.__writeVarint(makeZigZag(i32, 32))

  @writer
  def writeI64(self, i64):
    self.__writeVarint(makeZigZag(i64, 64))

  @writer
  def writeDouble(self, dub):
    self.trans.write(pack('!d', dub))

  def __writeString(self, s):
    self.__writeSize(len(s))
    self.trans.write(str)
  writeString = writer(__writeString)

  def __readByte(self):
    result, = unpack(self.trans.readAll(1))
    return result

  def __readVarint(self):
    result = 0
    shift = 0
    while True:
      byte = self.trans.readAll(1)
      result |= (b & 0xf7) << shift
      if byte >> 7:
        return result
      shift += 7
  
  def __readZigZag(self):
    return fromZigZag(self.__readVarint)

  def __getTType(self, byte):
    return TTYPES[byte & 0x0f]
    
  def __readSize(self):
    result = self.__readZigZag()
    if result > 0x7fff:
      raise TException("Length is too long")
    return result

  def readMessageBegin(self):
    assert self.state == CLEAR
    proto_id = self.__readByte()
    if proto_id != self.PROTOCOL_ID:
      raise TProtocolException(TProtocolException.BAD_VERSION, 
          'Bad protocol id in the message: %d' % proto_id)
    ver_type = self.__readByte()
    type = (ver_type & self.TYPE_MASK) >> self.SHIFT_AMOUNT
    version = ver_type & self.VERSION_MASK
    if version != self.VERSION:
      raise TProtocolException(TProtocolException.BAD_VERSION, 
          'Bad version: %d (expect %d)' % (version, self.VERSION))
    seqid = self.__readVarint()
    name = self.__readString()
    return name, type, seqid

  def readMessageEnd(self):
    assert self.state == READ
    assert len(self.__structs) == 0
    self.state = CLEAR

  def readStructBegin(self):
    assert self.state == CLEAR or self.state == READ or \
          self.state == CONTAINER_READ
    self.__structs.append((self.state, self.__last))
    self.state = READ
    self.__last = 0

  def readStructEnd(self):
    assert self.state == READ
    self.state, self.__last = self.__structs.pop()

  def readCollectionBegin(self):
    assert self.state == VALUE_READ
    self.state = CONTAINER_READ
    size_type = self.__readByte()
    type = self.__getTType(size)
    if size_type >> 4 == 15:
      return type, self.__readSize()
    else:
      return type, size_type >> 4
  readSetBegin = readCollectionBegin
  readListBegin = readCollectionBegin

  def readMapBegin(self):
    assert self.state == VALUE_READ
    self.state = CONTAINER_READ
    size = self.__readSize()
    types = 0
    if size > 0:
      types = self.__readByte()
    vtype = self.__getTType(types)
    ktype = self.__getTType(types >> 4)
    return ktype, vtype, size

  def readCollectionEnd(self):
    assert self.state == CONTAINER_READ
    self.state = CLEAR
  readSetEnd = readCollectionEnd
  readListEnd = readCollectionEnd
  readMapEnd = readCollectionEnd

  def readBool(self):
    if self.state == TRUE_READ:
      return True
    elif self.state == FALSE_READ:
      return False
    elif self.state == CONTAINER_READ:
      return bool(self.__readByte())
    else:
      raise AssertetionError, "Invalid state"

  readByte = reader(__readByte)
  readI16 = reader(__readZigZag)
  readI32 = reader(__readZigZag)
  readI64 = reader(__readZigZag)
  
  @reader
  def readDouble(self):
    buff = self.trans.readAll(8)
    val, = unpack('!d', buff)
    return val

  def __readString(self):
    len = self.__readSize()
    return self.trans.readAll(len)
  readString = reader(__readString)

class TCompactProtocolFactory:
  def __init__(self):
    pass

  def getProtocol(self, trans):
    return TCompactProtocol(trans)