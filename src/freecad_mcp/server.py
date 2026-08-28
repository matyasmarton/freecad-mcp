import mcp.types as types
from mcp.server import Server
import anyio
import argparse
from mcp.server.stdio import stdio_server

server = Server("freecad")
@server.list_tools()
async def list_tools():
    return [ types.Tool(
       name="create_document",            # ← a plain string, not a schema dict
       description=" Creates a new FreeCAD document",                  # ← written for the LLM
       inputSchema={                      # ← the JSON Schema dict that describes ARGUMENTS
           "type": "object",
           "properties": {
               "name": {"type": "string", "minLength": 1},   # ← Decision 2 lives HERE
           },
           "required": ["name"],
           "additionalProperties": False,  # ← also a schema keyword, inside inputSchema
       },
   )]

@server.call_tool() 
async def call_tool(name,arguments):
    if name == "create_document":
         return await handle_create_document(arguments)
    return [{"type":"text", "text":f"unknown tool: {name}"}]

async def run_server():
	async with stdio_server() as (read_stream, write_stream):
		await server.run(read_stream, write_stream, server.create_initialization_options())


async def handle_create_document(arguments):
    import FreeCAD
    doc_name = arguments["name"]
    docs = FreeCAD.listDocuments()
    if doc_name in docs:
        return   types.CallToolResult(content=[{"type":"text","text":"Error"}],isError=True)
    else: 
        FreeCAD.newDocument(doc_name)
        return [{"type":"text","text":f" {doc_name} created!"}]

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
