from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.session import ClientSession
import anyio


    

async def main():
    # 1. Define the command to launch your local server
    server_params = StdioServerParameters(
        command = "/Users/Meltwater_User/freecad-mcp/.venv/bin/python",
        args = ["-m", "freecad_mcp.server", "--transport", "stdio"],
        env = None,
        cwd = "/Users/Meltwater_User/freecad-mcp"
     ) 

    async with stdio_client(server_params) as (read_stream, write_stream):

        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()


            tools = await session.list_tools()
            print("Available tools:", tools)



anyio.run(main)
    
