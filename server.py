import asyncio                         # 使用 asyncio 建立裸 TCP 服务器
from struct import pack, unpack        # 编解码 4 字节小端整数

HOST = "0.0.0.0"                       # 监听全部 IPv4 地址
PORT = 8000                            # 裸 TCP 端口
db = {}                                # key -> [[votes, payload], ...]

async def read_u32(reader):            # 精确读取一个 4 字节小端无符号整数
    return unpack("<I", await reader.readexactly(4))[0]  # 读取并转换整数

async def read_data(reader):           # 读取 [4B size][data]
    size = await read_u32(reader)       # 先读取数据长度
    return await reader.readexactly(size)  # 再读取指定长度的数据

async def handle(reader, writer):      # 每条连接只处理一个操作，完成后关闭
    try:                               # 捕获断线和格式错误
        op = (await reader.readexactly(1))[0]  # 第一个字节就是操作码
        key = await read_data(reader)  # 所有操作的第一个参数都是 key

        if op == 1:                    # 投票请求：[1][key-size][key][4B idx]
            idx = await read_u32(reader)  # idx 固定为 4 字节，不再添加多余 size
            item = db[key][idx]        # 找到要投票的项目
            item[0] += 1               # 票数加一
            writer.write(pack("<I", item[0]))  # 响应只有 4 字节新票数

        elif op == 2:                  # 获取请求：[2][key-size][key]
            items = db.get(key)        # 找到该 key 下的数据
            if items:                  # 有数据才发送响应
                votes, payload = max(items, key=lambda item: item[0])  # 取票数最高且最早插入的第一个 data
                writer.write(pack("<I", len(payload)))  # 响应先发 4 字节 payload 长度
                writer.write(payload)  # 紧接着发送 payload，不发送 votes 等多余信息

        elif op == 3:                  # 上传请求：[3][key-size][key][payload-size][payload]
            payload = await read_data(reader)  # 读取要上传的 payload
            db[key] = [[0, payload]]      # 覆盖同 key（编辑器"改动即上传"需最新版本胜出）
            writer.write(pack("<I", 0))   # 响应只有 4 字节 idx

        await writer.drain()           # 把响应送入系统发送缓冲
    except (asyncio.IncompleteReadError, ConnectionError, KeyError, IndexError):  # 客户端断线或请求无效
        pass                           # 最低限度协议不额外发送错误文本
    finally:                           # 无论成功失败都关闭本次连接
        writer.close()                 # 关闭写端
        try:                           # 等待连接真正关闭
            await writer.wait_closed()  # 释放 socket
        except ConnectionError:        # 对端提前关闭时忽略异常
            pass                       # 不发送任何额外数据

async def main():                      # 服务器入口
    server = await asyncio.start_server(handle, HOST, PORT)  # 创建裸 TCP 服务器
    async with server:                 # 退出时自动释放监听 socket
        await server.serve_forever()   # 永久接受连接

if __name__ == "__main__":            # 直接运行本文件时启动服务器
    asyncio.run(main())                # 运行异步事件循环
