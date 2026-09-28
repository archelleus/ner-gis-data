#!/usr/bin/env python3
"""
Lightweight Static Development Server with HTTP Range Request Support
Supports PMTiles and Cloud-Optimized GeoTIFF streaming via HTTP 206 Partial Content
and CORS headers.
"""

import http.server
import os
import re
import socketserver
import sys

DEFAULT_PORT = 8080
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class RangeRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT_DIR, **kwargs)

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Range, Content-Type, Accept-Encoding")
        self.send_header("Access-Control-Expose-Headers", "Content-Range, Content-Length, Accept-Ranges")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def do_GET(self):
        range_header = self.headers.get("Range")
        if not range_header or not range_header.startswith("bytes="):
            return super().do_GET()

        path = self.translate_path(self.path)
        if not os.path.isfile(path):
            return super().do_GET()

        file_size = os.path.getsize(path)
        ranges = re.findall(r"(\d+)-(\d*)", range_header)
        if not ranges:
            return super().do_GET()

        start_str, end_str = ranges[0]
        start = int(start_str)
        end = int(end_str) if end_str else file_size - 1
        if end >= file_size:
            end = file_size - 1

        if start > end or start >= file_size:
            self.send_response(416)  # Range Not Satisfiable
            self.send_header("Content-Range", f"bytes */{file_size}")
            self.end_headers()
            return

        content_length = end - start + 1

        self.send_response(206)  # Partial Content
        content_type = self.guess_type(path)
        if path.endswith(".pmtiles"):
            content_type = "application/vnd.pmtiles"
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
        self.send_header("Content-Length", str(content_length))
        self.end_headers()

        with open(path, "rb") as f:
            f.seek(start)
            remaining = content_length
            chunk_size = 64 * 1024
            while remaining > 0:
                read_size = min(chunk_size, remaining)
                data = f.read(read_size)
                if not data:
                    break
                self.wfile.write(data)
                remaining -= len(data)


def find_free_port(start_port):
    import socket
    port = start_port
    while port < start_port + 100:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
        port += 1
    return start_port


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else find_free_port(DEFAULT_PORT)
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("0.0.0.0", port), RangeRequestHandler) as httpd:
        print(f"Server started at http://localhost:{port}/web/")
        print(f"Serving root directory: {ROOT_DIR}")
        print("HTTP Range Requests and CORS enabled.")
        sys.stdout.flush()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server.")


if __name__ == "__main__":
    main()
