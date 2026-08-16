import mcp.types as types
from mcp.server import Server
import anyio
import argparse
from mcp.server.stdio import stdio_server

server = Server("freecad")
@server.list_tools()
async def list_tools():
	return []

@server.call_tool() 
async def call_tool(name,arguments):
	return [types.TextContent(type="text", text="not implemented")]

async def run_server():
	async with stdio_server() as (read_stream, write_stream):
		await server.run(read_stream, write_stream, server.create_initialization_options())




def main():
	parser = argparse.ArgumentParser()
	parser.add_argument("-t", "--transport",choices=["stdio", "http"],default="stdio")
	parser.add_argument("--host",default="0.0.0.0")
	parser.add_argument("-p", "--port",type=int, default=8000)
	args = parser.parse_args()
	if args.transport == 'stdio':
		 anyio.run(run_server)
	else:
		raise NotImplementedError


if __name__ == "__main__":
    main()
