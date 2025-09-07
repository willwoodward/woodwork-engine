from typing import Literal
from woodwork.components.mcp.mcp_base import mcp
from woodwork.deployments.docker import Docker
from woodwork.utils import format_kwargs

from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.sse import sse_client
from mcp import ClientSession
import asyncio
from urllib.parse import urlparse
import os


class mcp_server(mcp):
    def __init__(
        self,
        transport: Literal["stdio", "sse"],
        image_url: str = None,
        api_key: str = None,
        remote_url: str = None,
        **config
    ):
        """
        :param transport: "stdio" for local Docker server, "sse" for remote HTTP/SSE server
        :param image_url: Docker image for local stdio server (required for stdio)
        :param api_key: GitHub token (PAT) for remote SSE server
        :param remote_url: SSE URL for remote MCP server (required for sse)
        """
        format_kwargs(config, type="server", transport=transport)
        super().__init__(**config)

        self.transport = transport
        self.image_url = image_url
        self.api_key = api_key
        self.remote_url = remote_url

        self.docker = None
        self.client_reader = None
        self.client_writer = None
        self.session = None

        # Automatically connect
        asyncio.run(self.connect())

    async def connect(self):
        if self.transport == "stdio":
            if not self.image_url:
                raise ValueError("image_url is required for stdio transport")

            self.docker = Docker(
                image_name="ghcr.io/github/github-mcp-server",
                container_name=self.name,
                dockerfile=None,
                container_args={
                    "environment": {
                        "GITHUB_PERSONAL_ACCESS_TOKEN": self.api_key
                    },
                    "network_mode": "host",
                    "stdin_open": True,
                },
            )
            self.docker.init()

            params = StdioServerParameters(
                command="docker",
                args=[
                    "exec", "-i", self.name, "github-mcp-server",
                ],
            )
            async with stdio_client(params) as (reader, writer):
                self.client_reader = reader
                self.client_writer = writer
                self.session = ClientSession(reader, writer)
                await self.session.initialize()

        elif self.transport == "http":
            if not self.remote_url or urlparse(self.remote_url).scheme not in ("http", "https"):
                raise ValueError("remote_url must be a valid HTTP/SSE URL for sse transport")
            if not self.api_key:
                raise ValueError("api_key (PAT) is required for remote SSE transport")

            headers = {"Authorization": f"Bearer {self.api_key}"}
            async with sse_client(self.remote_url, headers=headers) as streams:
                self.session = ClientSession(streams[0], streams[1])
                await self.session.initialize()

        else:
            raise ValueError(f"Unsupported transport: {self.transport}")

    async def list_tools(self):
        if not self.session:
            await self.connect()
        return await self.session.list_tools()

    async def list_resources(self):
        if not self.session:
            await self.connect()
        return await self.session.list_resources()

    async def call_tool(self, tool_name, **kwargs):
        if not self.session:
            await self.connect()
        return await self.session.call_tool(tool_name, kwargs)

    def input(self):
        return None

    @property
    def description(self):
        res = asyncio.run(self.list_tools())
        print(res)
        return res
