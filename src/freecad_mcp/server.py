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
   ),
   types.Tool(
    name="create_primitive",
    description=" Creates a new FreeCAD primitive: Box, Cylinder, or Sphere",
    inputSchema={                      # ← the JSON Schema dict that describes ARGUMENTS
           "type": "object",
           "properties": {
               "doc": {"type": "string", "minLength": 1}, 
               "type":{"type":"string", "enum":["Part::Box","Part::Cylinder","Part::Sphere"],"minLength":1},
               "length":{"type":"number", "exclusiveMinimum":0},
               "width":{"type":"number", "exclusiveMinimum":0},
               "height":{"type":"number", "exclusiveMinimum":0},
               "radius":{"type":"number", "exclusiveMinimum":0},
               "position":{"type":"array","items":{"type":"number"}, "minItems":3, "maxItems":3},
                
           },
           "required": ["doc","type"],
           "additionalProperties": False,  # ← also a schema keyword, inside inputSchema
       },
    
   )]

@server.call_tool() 
async def call_tool(name,arguments):
    if name == "create_document":
        return await handle_create_document(arguments)
    if name == "create_primitive":
        return await handle_create_primitive(arguments)
    
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
        
async def handle_create_primitive(arguments):
    import FreeCAD
    primitive = arguments["doc"]
    prim_type = arguments["type"]
    length = arguments.get("length")
    width = arguments.get("width")
    height = arguments.get("height")
    radius = arguments.get("radius")
    position = arguments.get("position")
    docs = FreeCAD.listDocuments()
    if primitive in docs:
        doc = docs[primitive]
    else:
        return types.CallToolResult(content=[{"type":"text","text":f"Error! Document '{primitive}' not found"}],isError=True)
    
   # prim_position = arguments["position"]
    if prim_type == "Part::Box":
        if length is None or width is None or height is None:
            return types.CallToolResult(content=[{"type":"text","text":"box needs length, width, height"}], isError=True)
    elif prim_type == "Part::Cylinder":
        if radius is None or height is None:
            return types.CallToolResult(content=[{"type":"text","text":"cylinder needs radius,  height"}], isError=True)
    elif prim_type == "Part::Sphere":
            if radius is None:
                return types.CallToolResult(content=[{"type":"text","text":"sphere  needs radius"}], isError=True)
    else:
         return  types.CallToolResult(content=[{"type":"text","text":f"unknown type {prim_type} "}],isError=True)

    if prim_type == "Part::Box":
        obj = doc.addObject("Part::Box")
        obj.Length = length
        obj.Width = width
        obj.Height = height
    elif prim_type == "Part::Cylinder":
        obj = doc.addObject("Part::Cylinder")
        obj.Radius = radius
        obj.Height = height
    elif prim_type == "Part::Sphere":
        obj = doc.addObject("Part::Sphere")
        obj.Radius = radius

    if position is not None:
        obj.Placement.Base = FreeCAD.Vector(position) 
        doc.recompute()
        return [{"type":"text","text":f" {obj.Name} from {primitive} created!"}]

    else:
        doc.recompute()
        return [{"type":"text","text":f" {obj.Name} from {primitive} created!"}]
        
    

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
