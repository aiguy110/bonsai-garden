#!/usr/bin/env python3
"""Relay TCP 127.0.0.1:PORT to a Unix socket: relay.py PORT SOCKET.

Runs inside the eval sandbox (no network), so pi's HTTP client can reach the tap,
which listens on a Unix socket mounted into the container.
"""
import asyncio
import sys

PORT, SOCK = int(sys.argv[1]), sys.argv[2]


async def pipe(reader, writer):
    try:
        while data := await reader.read(65536):
            writer.write(data)
            await writer.drain()
    except ConnectionError:
        pass
    finally:
        writer.close()


async def handle(cr, cw):
    try:
        ur, uw = await asyncio.open_unix_connection(SOCK)
    except OSError:
        cw.close()
        return
    await asyncio.gather(pipe(cr, uw), pipe(ur, cw))


async def main():
    server = await asyncio.start_server(handle, "127.0.0.1", PORT)
    async with server:
        await server.serve_forever()


asyncio.run(main())
