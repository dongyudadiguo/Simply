import socket, struct, hashlib, os

HOST = "124.221.146.23"
PORT = 9000

UPLOAD_FILE = 2
ADD_CHILD = 4
RECOMMEND_EDGE = 8

def sha(b):
    return hashlib.sha256(b).digest()

def conn():
    return socket.create_connection((HOST, PORT))

def recvn(s, n):
    b = b""
    while len(b) < n:
        x = s.recv(n - len(b))
        if not x:
            raise RuntimeError("closed")
        b += x
    return b

def upload(data):
    s = conn()

    s.sendall(bytes([UPLOAD_FILE]))
    s.sendall(struct.pack(">I", len(data)))
    s.sendall(data)

    st = recvn(s, 1)[0]
    if st:
        s.close()
        raise RuntimeError("upload failed")

    h = recvn(s, 32)

    s.close()
    return h

def add_child(parent, child):
    s = conn()

    s.sendall(bytes([ADD_CHILD]))
    s.sendall(parent)
    s.sendall(child)

    st = recvn(s, 1)[0]
    s.close()

    if st:
        raise RuntimeError("add_child failed")

def recommend(parent, child, id):
    s = conn()

    s.sendall(bytes([RECOMMEND_EDGE]))
    s.sendall(id)
    s.sendall(parent)
    s.sendall(child)

    st = recvn(s, 1)[0]
    s.close()

    if st:
        raise RuntimeError("recommend failed")

def block(data):
    return struct.pack("<i", len(data)) + data

def read_id():
    if not os.path.exists("id.bin"):
        raise RuntimeError("missing id.bin, register first")

    id = open("id.bin", "rb").read()

    if len(id) != 32:
        raise RuntimeError("bad id.bin")

    return id

def main():
    id = read_id()

    with open("first_editor.js", "rb") as f:
        editor_js = f.read()

    editor_hash = upload(editor_js)

    payload = b"FIRST_EDITOR"
    first_block = block(payload)
    first_block_hash = upload(first_block)

    p_editor = sha(payload)
    p_start = sha(b"Cstart")

    # 先建立普通边
    add_child(p_editor, editor_hash)
    add_child(p_start, first_block_hash)

    # 再推荐到最前
    recommend(p_editor, editor_hash, id)
    recommend(p_start, first_block_hash, id)

    print("editor js   ", editor_hash.hex())
    print("first block ", first_block_hash.hex())
    print("parent editor", p_editor.hex())
    print("parent start ", p_start.hex())
    print("recommended ok")

if __name__ == "__main__":
    main()