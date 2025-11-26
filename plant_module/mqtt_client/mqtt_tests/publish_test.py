import asyncio
import aiomqtt

async def main():
    async with \
    aiomqtt.Client(hostname="localhost", port=1883) as publisher,\
    aiomqtt.Client(hostname="localhost", port=1883) as subscriber:
        _ = await subscriber.subscribe("test")
        
        await publisher.publish("test", b"Hello, plebian.")
        
        async for message in subscriber.messages:
            if isinstance(message.payload, str):
                payload = message.payload
                print(f"Received: {payload}")
            else:
               continue  
            
            if payload == "Hello, plebian.":
                print("Received correct message, exiting...")
                return
            else:
                print("Received incorrect message, exiting...")
                return
        
if __name__ == "__main__":
    asyncio.run(main())