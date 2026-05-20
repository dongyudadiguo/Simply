import socket, struct

HOST = "124.221.146.23"
PORT = 9000
REGISTER = 1

def recvn(s, n):
    b = b""
    while len(b) < n:
        b += s.recv(n - len(b))
    return b

def register(token: str):
    data = token.encode()

    s = socket.create_connection((HOST, PORT))
    s.sendall(bytes([REGISTER]))
    s.sendall(struct.pack(">I", len(data)))
    s.sendall(data)

    st = recvn(s, 1)[0]

    if st:
        print("register failed")
        return None

    id = recvn(s, 32)
    s.close()

    return id

token = input("turnstile token: ")
id = register(token)

if id:
    open("id.bin", "wb").write(id)
    print(id.hex())