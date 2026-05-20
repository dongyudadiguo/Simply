import socket, struct, hashlib

HOST = "124.221.146.23"
PORT = 9000

UPLOAD_FILE = 2
ADD_CHILD = 4

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

    recvn(s, 1)
    h = recvn(s, 32)

    s.close()
    return h

def add_child(parent, child):
    s = conn()

    s.sendall(bytes([ADD_CHILD]))
    s.sendall(parent)
    s.sendall(child)

    recvn(s, 1)

    s.close()

def block(data):
    return struct.pack("<i", len(data)) + data

def main():
    with open("first_editor.js", "rb") as f:
        editor_js = f.read()

    editor_hash = upload(editor_js)

    payload = b"FIRST_EDITOR"
    first_block = block(payload)
    first_block_hash = upload(first_block)

    add_child(sha(payload), editor_hash)
    add_child(sha(b"Cstart"), first_block_hash)

    print("editor js   ", editor_hash.hex())
    print("first block ", first_block_hash.hex())
    print("sha(FIRST_EDITOR) -> editor js")
    print("sha(Cstart)       -> first block")

if __name__ == "__main__":
    main()